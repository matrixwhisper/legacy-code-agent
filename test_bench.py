import os
import pytest

from bench import (
    load_tasks,
    compile_and_run_cobol,
    parse_output_record,
    evaluate_fix,
)

TASKS_PATH = os.path.join(os.path.dirname(__file__), "tasks.jsonl")


def test_load_tasks_reads_all_entries():
    tasks = load_tasks(TASKS_PATH)
    assert len(tasks) >= 2
    ids = [t.task_id for t in tasks]
    assert "task_01_cobol_service_fee" in ids
    assert "task_04_cobol_double_bug" in ids


def test_task_fields_parsed_correctly():
    tasks = load_tasks(TASKS_PATH)
    task = next(t for t in tasks if t.task_id == "task_01_cobol_service_fee")
    assert task.language == "cobol"
    assert task.max_retries == 3
    assert len(task.hidden_tests) == 2


def test_parse_output_record_deny():
    lines = ["P001      DENY PATIENT LIABILITY EXCEEDS MAXIMUM THRESHOLD" + " " * 20 + "\n"]
    result = parse_output_record(lines)
    assert result["status"] == "DENY "
    assert "THRESHOLD" in result["reason"]


def test_parse_output_record_approve():
    header = "P001      APPRO" + " " * 65 + "\n"
    item_line = "01 ROOM CHARGES          720.00" + " " * 45 + "\n"
    result = parse_output_record([header, item_line])
    assert result["status"] == "APPRO"
    assert "ROOM CHARGES" in result["items"]


def test_buggy_task01_source_fails_hidden_tests():
    """
    Sanity check: the intentionally buggy source for task 1 should NOT
    pass its own hidden tests. If this test fails, the bug wasn't real.
    """
    tasks = load_tasks(TASKS_PATH)
    task = next(t for t in tasks if t.task_id == "task_01_cobol_service_fee")
    src_path = os.path.join(os.path.dirname(__file__), task.source_file)
    if not os.path.exists(src_path):
        pytest.skip("program_task01.cbl not created yet")

    with open(src_path) as f:
        buggy_source = f.read()

    result = evaluate_fix(task, buggy_source)
    assert result["all_passed"] is False


def test_correct_source_passes_task01_hidden_tests():
    """
    Sanity check the other direction: the clean, correct program.cbl
    SHOULD pass task 1's hidden tests, proving the test values themselves
    are accurate, not just biased toward detecting the bug.
    """
    tasks = load_tasks(TASKS_PATH)
    task = next(t for t in tasks if t.task_id == "task_01_cobol_service_fee")
    clean_path = os.path.join(os.path.dirname(__file__), "src", "program.cbl")
    if not os.path.exists(clean_path):
        pytest.skip("program.cbl not created yet")

    with open(clean_path) as f:
        clean_source = f.read()

    result = evaluate_fix(task, clean_source)
    assert result["all_passed"] is True



from generate_traj import trajectories_to_sft_pairs
from hillclimb import run_config, resolve_model_identifier


def test_trajectories_to_sft_pairs_keeps_only_successful():
    trajectories = [
        {
            "task_id": "task_a",
            "strategy": "single_shot",
            "original_source": "BAD CODE",
            "final_source": "STILL BAD",
            "passed": False,
            "retries_used": 0,
        },
        {
            "task_id": "task_a",
            "strategy": "iterative",
            "original_source": "BAD CODE",
            "final_source": "FIXED CODE",
            "passed": True,
            "retries_used": 2,
        },
    ]
    pairs = trajectories_to_sft_pairs(trajectories)
    assert len(pairs) == 1
    assert "FIXED CODE" in pairs[0]["response"]
    assert pairs[0]["retries_used"] == 2


def test_trajectories_to_sft_pairs_picks_fewest_retries():
    trajectories = [
        {
            "task_id": "task_b",
            "strategy": "single_shot",
            "original_source": "X",
            "final_source": "FIX_A",
            "passed": True,
            "retries_used": 0,
        },
        {
            "task_id": "task_b",
            "strategy": "iterative",
            "original_source": "X",
            "final_source": "FIX_B",
            "passed": True,
            "retries_used": 3,
        },
    ]
    pairs = trajectories_to_sft_pairs(trajectories)
    assert len(pairs) == 1
    assert "FIX_A" in pairs[0]["response"]


def test_trajectories_to_sft_pairs_skips_tasks_with_no_success():
    trajectories = [
        {
            "task_id": "task_c",
            "strategy": "single_shot",
            "original_source": "X",
            "final_source": "STILL WRONG",
            "passed": False,
            "retries_used": 0,
        },
    ]
    pairs = trajectories_to_sft_pairs(trajectories)
    assert len(pairs) == 0


def test_resolve_model_identifier_base_vs_finetuned():
    assert resolve_model_identifier(use_fine_tuned=False) == "claude-sonnet-4-5"
    assert resolve_model_identifier(use_fine_tuned=True) == "fine_tuned_adapter"


class _FakeTask:
    def __init__(self, task_id, difficulty="medium"):
        self.task_id = task_id
        self.difficulty = difficulty
        self.max_retries = 3
        self.source_file = None


def test_run_config_computes_pass_rate_correctly(monkeypatch, tmp_path):
    """
    Verifies hillclimb's aggregation math without calling a real model:
    fakes out single_shot_agent's return value entirely.
    """
    import hillclimb

    fake_source_file = tmp_path / "fake.cbl"
    fake_source_file.write_text("FAKE SOURCE")

    tasks = [_FakeTask("t1"), _FakeTask("t2"), _FakeTask("t3")]
    for t in tasks:
        t.source_file = str(fake_source_file)

    def fake_single_shot_agent(task, source, model_id):
        return {
            "passed": task.task_id != "t3",   # t1, t2 pass; t3 fails
            "retries_used": 0,
            "latency_seconds": 1.0,
        }

    monkeypatch.setattr(hillclimb, "single_shot_agent", fake_single_shot_agent)

    config = {
        "config_name": "test_config",
        "use_fine_tuned": False,
        "strategy": "single_shot",
        "max_retries_override": None,
    }
    result = hillclimb.run_config(config, tasks)

    assert result["pass_count"] == 2
    assert result["total_tasks"] == 3
    assert abs(result["pass_rate"] - (2 / 3)) < 1e-6