"""
Runs both agent strategies (single-shot and iterative) over every task,
logs full trajectories -- including failed attempts -- and converts them
into instruction/response training pairs for finetune.py.
"""
import json
import os
from dataclasses import asdict

from bench import load_tasks, single_shot_agent, iterative_agent

TASKS_PATH = "tasks.jsonl"
TRAJECTORIES_PATH = "trajectories.jsonl"
SFT_DATA_PATH = "sft_data.jsonl"
MODEL = "claude-sonnet-4-5"


def load_source_for_task(task) -> str:
    with open(task.source_file, "r") as f:
        return f.read()


def run_all_trajectories():
    tasks = load_tasks(TASKS_PATH)
    trajectories = []

    for task in tasks:
        original_source = load_source_for_task(task)

        print(f"[{task.task_id}] running single-shot agent...")
        single_result = single_shot_agent(task, original_source, MODEL)
        trajectories.append({
            "task_id": task.task_id,
            "strategy": "single_shot",
            "original_source": original_source,
            **single_result,
        })

        print(f"[{task.task_id}] running iterative agent...")
        iterative_result = iterative_agent(task, original_source, MODEL)
        trajectories.append({
            "task_id": task.task_id,
            "strategy": "iterative",
            "original_source": original_source,
            **iterative_result,
        })

    with open(TRAJECTORIES_PATH, "w") as f:
        for traj in trajectories:
            f.write(json.dumps(traj) + "\n")

    print(f"\nSaved {len(trajectories)} trajectories to {TRAJECTORIES_PATH}")
    return trajectories


def trajectories_to_sft_pairs(trajectories: list[dict]) -> list[dict]:
    """
    Converts trajectories into instruction/response pairs for fine-tuning.
    We keep successful fixes as positive examples. We also keep failed
    attempts paired with the eventual successful fix on the same task
    (when available), since that pairing is what makes the training
    data reflect real debugging behavior instead of just "correct answer
    memorization."
    """
    by_task = {}
    for traj in trajectories:
        by_task.setdefault(traj["task_id"], []).append(traj)

    sft_pairs = []
    for task_id, task_trajectories in by_task.items():
        successful = [t for t in task_trajectories if t["passed"]]
        if not successful:
            continue

        best = min(successful, key=lambda t: t["retries_used"])
        instruction = (
            f"You are an expert COBOL engineer. Fix the following program.\n\n"
            f"```cobol\n{best['original_source']}\n```"
        )
        response = f"```cobol\n{best['final_source']}\n```"

        sft_pairs.append({
            "task_id": task_id,
            "instruction": instruction,
            "response": response,
            "source_strategy": best["strategy"],
            "retries_used": best["retries_used"],
        })

    return sft_pairs


def main():
    trajectories = run_all_trajectories()
    sft_pairs = trajectories_to_sft_pairs(trajectories)

    with open(SFT_DATA_PATH, "w") as f:
        for pair in sft_pairs:
            f.write(json.dumps(pair) + "\n")

    print(f"Saved {len(sft_pairs)} SFT training pairs to {SFT_DATA_PATH}")


if __name__ == "__main__":
    main()