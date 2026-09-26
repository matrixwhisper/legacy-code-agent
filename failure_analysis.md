# CI Failure Analysis

## Overview

GitHub Actions successfully installed the project dependencies and collected 11 tests. The initial CI run completed with **9 passed and 2 failed**. After the first corrections, a second run completed with **10 passed and 1 failed**.

The failures were caused by inconsistencies between the test fixtures, task identifiers, and the benchmark's output-parsing logic. There were no dependency-installation or workflow-configuration failures involved in these test failures.

---

## Failure 1: Task ID Mismatch

### Test

`test_load_tasks_reads_all_entries`

### Symptom

The test expected the task identifier:

```text
task_04_cobol_double_bug
```

However, the second entry in `tasks.jsonl` used:

```text
task_cobol_double_bug
```

The test therefore failed when checking that the expected task ID was present.

### Root Cause

The task fixture and the test suite used different identifiers for the same benchmark task.

### Resolution

The task ID in `tasks.jsonl` was updated to:

```text
task_04_cobol_double_bug
```

This resolved the task-ID failure.

---

## Failure 2: Task 1 Expected Values

### Test

`test_correct_source_passes_task01_hidden_tests`

### Symptom

The test initially failed because the expected service-fee and total-bill values in `tasks.jsonl` did not match the calculations produced by the clean COBOL source.

### Root Cause

The expected values in the task fixture were inconsistent with the billing calculation implemented by `src/program.cbl`.

The source calculates the service fee as **6.5% of the subtotal**, where the subtotal consists of the room charge and procedure cost.

The corrected expected values are:

| Input | Subtotal | Service Fee | Total Bill |
|---|---:|---:|---:|
| P001 | $6,870.00 | $446.55 | $7,316.55 |
| P002 | $6,960.00 | $452.40 | $7,412.40 |

### Resolution

The expected values in `tasks.jsonl` were corrected to match the deterministic calculations produced by the clean COBOL implementation.

This correction resolved the task-fixture mismatch.

---

## Failure 3: Missing `total_bill` in Parsed Output

### Test

`test_correct_source_passes_task01_hidden_tests`

### Symptom

After the task ID and fixture corrections, the second CI run completed with **10 passed and 1 failed**.

The remaining failure occurred because:

```python
result["all_passed"]
```

was `False`.

The evaluator compares expected fields against the dictionary produced by `parse_output_record()`.

### Root Cause

The COBOL program does not emit a dedicated `total_bill` output record. Instead, the approval output contains separate item lines for:

- Room charges
- Procedure cost
- Service fee

The parser therefore had no `total_bill` field available for the evaluator to compare against the expected value.

### Resolution

`bench.py` was updated to derive `total_bill` from the parsed room, procedure, and service-fee amounts using decimal arithmetic.

This allowed the evaluator to verify the expected total without requiring the COBOL program to emit an additional output record.

---

## Verification

After applying the corrections:

1. The task ID in `tasks.jsonl` was aligned with the test suite.
2. Task 1 expected billing values were corrected.
3. `bench.py` was updated to derive `total_bill` from the parsed output.
4. The subsequent GitHub Actions run completed successfully.

### Final CI Result

**11 tests passed, 0 failed.**

---

## Engineering Takeaways

These failures highlighted several important aspects of the benchmark:

- **Task fixtures must remain consistent with the reference implementation.**
- **Task identifiers must be consistent across task definitions and tests.**
- **Evaluation logic must account for the actual output contract of the target program.**
- **Compilation success alone is insufficient for evaluating generated legacy-code fixes.**
- **Deterministic hidden-test evaluation provides a stronger correctness signal than checking whether generated code merely compiles.**

The debugging process also exposed an important distinction between **program output representation** and **evaluation representation**: a value does not necessarily need to be emitted explicitly by the legacy program if it can be deterministically derived from validated output fields.