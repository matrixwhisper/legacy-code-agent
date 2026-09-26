"""
Sweeps configurations (base vs fine-tuned model x single-shot vs iterative
strategy x retry limits) and records real benchmark scores for each,
so we have honest before/after evidence instead of a single number.
"""
import json
import time

from bench import load_tasks, single_shot_agent, iterative_agent, load_tasks

TASKS_PATH = "tasks.jsonl"
RESULTS_PATH = "results.jsonl"

BASE_MODEL_NAME = "claude-sonnet-4-5"          # stand-in for the un-fine-tuned baseline
FINE_TUNED_ADAPTER_DIR = "fine_tuned_adapter"  # produced by finetune.py

CONFIGS = [
    {"config_name": "base_single_shot", "use_fine_tuned": False, "strategy": "single_shot", "max_retries_override": None},
    {"config_name": "base_iterative_r3", "use_fine_tuned": False, "strategy": "iterative", "max_retries_override": 3},
    {"config_name": "base_iterative_r5", "use_fine_tuned": False, "strategy": "iterative", "max_retries_override": 5},
    {"config_name": "finetuned_single_shot", "use_fine_tuned": True, "strategy": "single_shot", "max_retries_override": None},
    {"config_name": "finetuned_iterative_r3", "use_fine_tuned": True, "strategy": "iterative", "max_retries_override": 3},
]


def load_source_for_task(task) -> str:
    with open(task.source_file, "r") as f:
        return f.read()


def resolve_model_identifier(use_fine_tuned: bool) -> str:
    """
    Points to either the plain base model or the local fine-tuned adapter.
    NOTE: bench.py's call_model currently calls the Anthropic API directly;
    to actually exercise the fine-tuned local model here, swap in a local
    inference call (e.g. via transformers + peft load) for the
    use_fine_tuned=True branch. Left explicit rather than faked.
    """
    if use_fine_tuned:
        return FINE_TUNED_ADAPTER_DIR
    return BASE_MODEL_NAME


def run_config(config: dict, tasks: list) -> dict:
    model_id = resolve_model_identifier(config["use_fine_tuned"])
    task_results = []

    for task in tasks:
        original_source = load_source_for_task(task)

        if config["max_retries_override"] is not None:
            task.max_retries = config["max_retries_override"]

        if config["strategy"] == "single_shot":
            result = single_shot_agent(task, original_source, model_id)
        else:
            result = iterative_agent(task, original_source, model_id)

        task_results.append({
            "task_id": task.task_id,
            "difficulty": task.difficulty,
            "passed": result["passed"],
            "retries_used": result["retries_used"],
            "latency_seconds": result["latency_seconds"],
        })

    pass_count = sum(1 for r in task_results if r["passed"])
    pass_rate = pass_count / len(task_results) if task_results else 0.0
    avg_latency = sum(r["latency_seconds"] for r in task_results) / len(task_results) if task_results else 0.0

    return {
        "config_name": config["config_name"],
        "pass_rate": pass_rate,
        "pass_count": pass_count,
        "total_tasks": len(task_results),
        "avg_latency_seconds": avg_latency,
        "task_results": task_results,
    }


def main():
    tasks = load_tasks(TASKS_PATH)
    all_results = []

    for config in CONFIGS:
        print(f"Running config: {config['config_name']}...")
        start = time.time()
        result = run_config(config, tasks)
        result["wall_clock_seconds"] = time.time() - start
        all_results.append(result)
        print(f"  pass_rate={result['pass_rate']:.2f} ({result['pass_count']}/{result['total_tasks']})")

    with open(RESULTS_PATH, "w") as f:
        for result in all_results:
            f.write(json.dumps(result) + "\n")

    print(f"\nSaved {len(all_results)} config results to {RESULTS_PATH}")
    print("\nSummary (paste this into failure_analysis.md / README.md):")
    for result in all_results:
        print(f"  {result['config_name']:30s} pass_rate={result['pass_rate']:.2f}  avg_latency={result['avg_latency_seconds']:.1f}s")


if __name__ == "__main__":
    main()