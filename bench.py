"""
Core benchmark harness: task loading, sandboxed COBOL execution,
two agent strategies (single-shot vs iterative), and evaluation metrics.
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from typing import Optional



@dataclass
class HiddenTest:
    input: str
    expected: dict = field(default_factory=dict)


@dataclass
class Task:
    task_id: str
    title: str
    language: str
    difficulty: str
    description: str
    source_file: str
    max_retries: int
    timeout_seconds: int
    hidden_tests: list[HiddenTest]


def load_tasks(path: str) -> list[Task]:
    tasks = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            raw = json.loads(line)
            hidden_tests = [
                HiddenTest(input=ht["input"], expected={k: v for k, v in ht.items() if k != "input"})
                for ht in raw["hidden_tests"]
            ]
            tasks.append(Task(
                task_id=raw["task_id"],
                title=raw["title"],
                language=raw["language"],
                difficulty=raw["difficulty"],
                description=raw["description"],
                source_file=raw["source_file"],
                max_retries=raw.get("max_retries", 3),
                timeout_seconds=raw.get("timeout_seconds", 20),
                hidden_tests=hidden_tests,
            ))
    return tasks


# ---------------------------------------------------------------------------
# 2. Sandbox: compiles + runs a COBOL source against one input line
# ---------------------------------------------------------------------------

def compile_and_run_cobol(source_code: str, input_line: str, timeout: int) -> dict:
    """
    Writes source_code to a temp dir, compiles with GnuCOBOL (cobc),
    runs it against a single input line, and parses the output record(s).
    Returns a dict with keys: status ("ok"/"compile_error"/"timeout"/"runtime_error"),
    and if ok: parsed fields from OUTPUT.DAT.
    """
    workdir = tempfile.mkdtemp(prefix="cobol_sandbox_")
    try:
        os.makedirs(os.path.join(workdir, "src"), exist_ok=True)
        os.makedirs(os.path.join(workdir, "record"), exist_ok=True)

        src_path = os.path.join(workdir, "src", "program.cbl")
        with open(src_path, "w") as f:
            f.write(source_code)

        with open(os.path.join(workdir, "src", "INPUT.DAT"), "w") as f:
            f.write(input_line + "\n")

        binary_path = os.path.join(workdir, "program_bin")
        compile_proc = subprocess.run(
            ["cobc", "-x", "-o", binary_path, src_path],
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if compile_proc.returncode != 0:
            return {"status": "compile_error", "stderr": compile_proc.stderr}

        try:
            run_proc = subprocess.run(
                [binary_path],
                cwd=workdir,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return {"status": "timeout"}

        output_path = os.path.join(workdir, "record", "OUTPUT.DAT")
        if not os.path.exists(output_path):
            return {"status": "runtime_error", "stderr": run_proc.stderr}

        with open(output_path, "r") as f:
            raw_lines = f.readlines()

        return {"status": "ok", "parsed": parse_output_record(raw_lines)}
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def parse_output_record(lines: list[str]) -> dict:
    """
    Parses fixed-width OUTPUT.DAT lines produced by HOSPITAL01-style programs.
    Handles both the DENY record and the APPROVE header + item lines.
    """
    result = {}
    if not lines:
        return result

    header = lines[0]
    status = header[10:15]
    result["status"] = status

    if status.strip() == "DENY":
        result["reason"] = header[15:60].strip()
        return result

    # APPROVE case: subsequent lines are item records
    items = {}
    for line in lines[1:]:
        if len(line) < 36:
            continue
        description = line[3:23].strip()
        sign = line[23:24]
        amount_str = line[24:35].replace(".", "")
        try:
            amount = int(amount_str) / 100.0
        except ValueError:
            continue
        if sign == "-":
            amount = -amount
        items[description] = f"{amount:.2f}"
    result["items"] = items

    # convenience aliases used by hidden test expectations
    if "SERVICE FEE" in items:
        result["service_fee"] = items["SERVICE FEE"]
    if "PATIENT OWES" in items:
        result["patient_owes"] = items["PATIENT OWES"]
    return result


def evaluate_fix(task: Task, candidate_source: str) -> dict:
    """
    Runs candidate_source against every hidden test in the task.
    Returns per-test pass/fail plus a human-readable failure summary
    (used to feed back into the iterative agent).
    """
    test_results = []
    all_passed = True

    for ht in task.hidden_tests:
        run_result = compile_and_run_cobol(candidate_source, ht.input, task.timeout_seconds)

        if run_result["status"] != "ok":
            all_passed = False
            test_results.append({
                "input": ht.input,
                "passed": False,
                "reason": f"execution failed: {run_result['status']}",
                "detail": run_result.get("stderr", ""),
            })
            continue

        parsed = run_result["parsed"]
        mismatches = []
        for key, expected_value in ht.expected.items():
            field_name = key.replace("expected_", "")
            actual_value = parsed.get(field_name) or parsed.get("items", {}).get(field_name.upper().replace("_", " "))
            if str(actual_value) != str(expected_value):
                mismatches.append(f"{field_name}: expected {expected_value}, got {actual_value}")

        passed = len(mismatches) == 0
        all_passed = all_passed and passed
        test_results.append({
            "input": ht.input,
            "passed": passed,
            "reason": "" if passed else "; ".join(mismatches),
        })

    return {"all_passed": all_passed, "test_results": test_results}



def call_model(system_prompt: str, user_prompt: str, model: str = "claude-sonnet-4-5") -> str:
    """
    Thin wrapper around the Anthropic API. Requires ANTHROPIC_API_KEY in env.
    Returns the raw text response.
    """
    import anthropic
    client = anthropic.Anthropic()
    response = client.messages.create(
        model=model,
        max_tokens=4000,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return "".join(block.text for block in response.content if block.type == "text")


def extract_code_block(text: str) -> str:
    match = re.search(r"```(?:cobol)?\n(.*?)```", text, re.DOTALL)
    return match.group(1) if match else text


SYSTEM_PROMPT = (
    "You are an expert COBOL engineer. You will be given a buggy COBOL program "
    "and a description of the observed problem. Return the FULL corrected COBOL "
    "source file inside a single ```cobol code block, with no other commentary."
)


def single_shot_agent(task: Task, original_source: str, model: str) -> dict:
    start = time.time()
    prompt = f"Task: {task.description}\n\nCurrent source:\n```cobol\n{original_source}\n```"
    response_text = call_model(SYSTEM_PROMPT, prompt, model)
    candidate = extract_code_block(response_text)
    eval_result = evaluate_fix(task, candidate)
    return {
        "strategy": "single_shot",
        "passed": eval_result["all_passed"],
        "retries_used": 0,
        "latency_seconds": time.time() - start,
        "final_source": candidate,
        "test_results": eval_result["test_results"],
    }


def iterative_agent(task: Task, original_source: str, model: str) -> dict:
    start = time.time()
    current_source = original_source
    history = []

    for attempt in range(task.max_retries + 1):
        if attempt == 0:
            prompt = f"Task: {task.description}\n\nCurrent source:\n```cobol\n{current_source}\n```"
        else:
            last = history[-1]
            failures = "\n".join(
                f"- input {r['input']}: {r['reason']}"
                for r in last["test_results"] if not r["passed"]
            )
            prompt = (
                f"Your previous fix still fails these hidden tests:\n{failures}\n\n"
                f"Your previous source:\n```cobol\n{current_source}\n```\n"
                "Return a corrected full source file."
            )

        response_text = call_model(SYSTEM_PROMPT, prompt, model)
        candidate = extract_code_block(response_text)
        eval_result = evaluate_fix(task, candidate)
        history.append({"attempt": attempt, "test_results": eval_result["test_results"]})
        current_source = candidate

        if eval_result["all_passed"]:
            return {
                "strategy": "iterative",
                "passed": True,
                "retries_used": attempt,
                "latency_seconds": time.time() - start,
                "final_source": current_source,
                "test_results": eval_result["test_results"],
            }

    return {
        "strategy": "iterative",
        "passed": False,
        "retries_used": task.max_retries,
        "latency_seconds": time.time() - start,
        "final_source": current_source,
        "test_results": history[-1]["test_results"],
    }