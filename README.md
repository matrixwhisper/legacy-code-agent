# Legacy Code Agent

<p align="center">
  <strong>LLM Agent Benchmark for Legacy COBOL Code with QLoRA Fine-Tuning</strong>
</p>

<p align="center">
  An experimental agentic system that uses LLMs to analyze and modify legacy COBOL programs, evaluates generated code through real compilation and hidden tests, records agent trajectories, and uses successful trajectories to create supervised fine-tuning data for Qwen2.5-Coder.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/PyTorch-2.3%2B-EE4C2C?logo=pytorch&logoColor=white" alt="PyTorch">
  <img src="https://img.shields.io/badge/Hugging%20Face-Transformers-FFD21E?logo=huggingface&logoColor=black" alt="Hugging Face Transformers">
  <img src="https://img.shields.io/badge/PEFT-LoRA%2FQLoRA-FF6F00?logo=huggingface&logoColor=white" alt="PEFT LoRA QLoRA">
  <img src="https://img.shields.io/badge/Qwen2.5--Coder-1.5B-7C3AED" alt="Qwen2.5-Coder">
  <img src="https://img.shields.io/badge/COBOL-Legacy%20Systems-00599C" alt="COBOL">
  <img src="https://img.shields.io/badge/Anthropic-Claude-191919?logo=anthropic&logoColor=white" alt="Anthropic Claude">
  <img src="https://img.shields.io/badge/Pytest-Testing-0A9EDC?logo=pytest&logoColor=white" alt="Pytest">
  <img src="https://img.shields.io/badge/BitsAndBytes-4--bit%20Quantization-555555" alt="BitsAndBytes">
</p>

---

## Overview

**Legacy Code Agent** is an experimental LLM-based system designed around the problem of working with legacy COBOL programs.

Instead of evaluating an LLM only by whether it produces syntactically valid code, the system places generated COBOL inside an execution-based benchmark:

```text
COBOL Task
    │
    ▼
LLM Agent
    │
    ├── Single-Shot Strategy
    │
    └── Iterative Strategy
            │
            ▼
       Generated COBOL
            │
            ▼
       GnuCOBOL Compiler
            │
            ▼
      Sandboxed Execution
            │
            ▼
       Hidden Test Cases
            │
       ┌────┴────┐
       ▼         ▼
     PASS      FAIL
                 │
                 ▼
          Feedback to Agent
                 │
                 ▼
             Retry
```

Successful agent trajectories can then be transformed into supervised fine-tuning examples and used to fine-tune **Qwen2.5-Coder-1.5B-Instruct using QLoRA**.

---

## Key Features

- 🤖 **LLM-powered COBOL coding agent**
- 🔄 **Single-shot and iterative agent strategies**
- 🧪 **Execution-based hidden-test evaluation**
- 🏗️ **Real COBOL compilation using GnuCOBOL**
- 🔒 **Temporary sandbox execution environment**
- ⏱️ **Execution timeout handling**
- 📊 **Per-test evaluation and failure reporting**
- 📝 **Agent trajectory collection**
- 🧠 **Self-generated supervised fine-tuning data**
- ⚡ **QLoRA parameter-efficient fine-tuning**
- 🧩 **Qwen2.5-Coder-1.5B-Instruct**
- 📈 **Trajectory and failure analysis**
- 🧪 **Pytest-based automated testing**

---

# Architecture

The project consists of several connected stages.

## 1. COBOL Benchmark

Tasks are defined in `tasks.jsonl`.

Each task contains information such as:

```json
{
  "task_id": "task_01_cobol_service_fee",
  "title": "Hospital billing service fee miscalculated",
  "language": "cobol",
  "difficulty": "medium",
  "description": "...",
  "source_file": "src/program_task01.cbl",
  "max_retries": 3,
  "timeout_seconds": 20,
  "hidden_tests": []
}
```

The benchmark currently includes COBOL tasks involving business-logic bugs such as:

- Incorrect billing calculations
- Insurance payout logic
- Patient liability calculations
- Approval and denial decisions

---

## 2. Agent Strategies

The benchmark evaluates two approaches.

### Single-Shot Agent

The single-shot agent receives:

```text
Task description
+
Original COBOL source
```

and produces a complete replacement COBOL source file.

The generated program is then compiled and tested.

```text
Task
  ↓
Claude
  ↓
COBOL candidate
  ↓
Compile
  ↓
Hidden tests
```

---

### Iterative Agent

The iterative strategy adds execution feedback.

```text
Original COBOL
       ↓
     Claude
       ↓
 Candidate #1
       ↓
 Hidden Tests
       ↓
   Failures
       ↓
 Failure Feedback
       ↓
     Claude
       ↓
 Candidate #2
       ↓
 Hidden Tests
       ↓
     ...
```

The process continues until the candidate passes all hidden tests or reaches the task's retry limit.

This allows the benchmark to evaluate whether an agent can use **execution feedback to improve a generated solution**.

---

# COBOL Execution Sandbox

One of the central components is the execution harness in `bench.py`.

For every generated COBOL candidate, the system:

1. Creates a temporary working directory.
2. Writes the generated source code.
3. Creates the required input file.
4. Compiles the program with GnuCOBOL.
5. Executes the compiled binary.
6. Applies a timeout.
7. Reads the generated `OUTPUT.DAT`.
8. Parses the fixed-width output.
9. Compares the result against hidden expectations.
10. Removes the temporary working directory.

Conceptually:

```text
Generated COBOL
      │
      ▼
Temporary Sandbox
      │
      ▼
    cobc
      │
      ▼
Compiled Program
      │
      ▼
   Execution
      │
      ▼
 OUTPUT.DAT
      │
      ▼
Output Parser
      │
      ▼
Hidden-Test Evaluation
```

This means the benchmark evaluates **program behavior**, not just generated text.

---

# Hidden-Test Evaluation

Each task contains hidden test cases.

For example, the hospital billing benchmark includes inputs such as:

```text
P001;John Doe;5000;STD;3000;4;REG
```

with expected values such as:

```text
expected_service_fee: 447.05
expected_total_bill: 7317.05
```

The candidate source must produce the expected behavior when actually executed.

A successful compilation alone is therefore not sufficient.

---

# Agent Trajectories

The `generate_traj.py` script runs both agent strategies across the benchmark.

For every task, it records information such as:

- Task ID
- Strategy
- Original source
- Final source
- Whether the solution passed
- Number of retries
- Latency
- Hidden-test results

The trajectories are written to:

```text
trajectories.jsonl
```

This creates a record of how the agents performed across the benchmark.

---

# Training Data Generation

Successful trajectories can be converted into supervised fine-tuning examples.

The generated dataset has the structure:

```text
instruction
response
source_strategy
retries_used
```

For example:

```text
Instruction:
You are an expert COBOL engineer. Fix the following program.

Response:
[corrected COBOL source]
```

The resulting dataset is saved as:

```text
sft_data.jsonl
```

This dataset becomes the input to the QLoRA training pipeline.

> Note: the current implementation uses successful trajectories as SFT examples. Failed attempts remain available in the trajectory/evaluation data rather than being directly emitted as separate SFT examples.

---

# QLoRA Fine-Tuning

The `finetune.py` script fine-tunes:

```text
Qwen/Qwen2.5-Coder-1.5B-Instruct
```

using parameter-efficient fine-tuning.

### Quantization

The model is loaded using:

- 4-bit quantization
- NF4 quantization
- Double quantization
- bfloat16 compute

### LoRA Configuration

```text
Rank:       16
Alpha:      32
Dropout:    0.05
Targets:    q_proj
            k_proj
            v_proj
            o_proj
```

### Training Configuration

```text
Maximum sequence length: 2048
Epochs:                  3
Learning rate:           2e-4
Batch size:              1
Gradient accumulation:  8
```

The resulting adapter is saved to:

```text
fine_tuned_adapter/
```

---

# Why QLoRA?

The project uses QLoRA to adapt a code-focused language model while keeping the base model quantized and training a comparatively small set of additional parameters.

The training pipeline combines:

```text
Qwen2.5-Coder
        +
4-bit Quantization
        +
LoRA Adapters
        +
COBOL Repair Examples
        ↓
Fine-Tuned Adapter
```

The project therefore combines **legacy-code benchmarking, agent trajectories, supervised fine-tuning, and parameter-efficient LLM adaptation** in one workflow.

---

# Project Structure

```text
legacy-code-agent/
│
├── .github/
│   └── workflows/
│
├── src/
│   ├── program_task01.cbl
│   └── program_task.cbl
│
├── README.md
├── pyproject.toml
├── tasks.jsonl
│
├── bench.py
├── generate_traj.py
├── finetune.py
├── hillclimb.py
│
├── results.jsonl
├── failure_analysis.md
└── test_bench.py
```

### Important files

| File | Purpose |
|---|---|
| `bench.py` | Benchmark harness, COBOL execution, agent strategies, and evaluation |
| `generate_traj.py` | Generates agent trajectories and SFT training pairs |
| `finetune.py` | QLoRA fine-tuning pipeline |
| `hillclimb.py` | Additional optimization/experimentation component |
| `tasks.jsonl` | Benchmark task definitions and hidden tests |
| `src/` | COBOL benchmark programs |
| `test_bench.py` | Automated benchmark tests |
| `results.jsonl` | Benchmark result records |
| `failure_analysis.md` | Failure analysis and observations |
| `pyproject.toml` | Python project configuration and dependencies |

---

# Requirements

## Software

- Python 3.10+
- GnuCOBOL
- Git
- A suitable environment for QLoRA training

The Python dependencies include:

- PyTorch
- Transformers
- PEFT
- BitsAndBytes
- Accelerate
- Datasets
- Anthropic
- Pytest

---

# Installation

Clone the repository:

```bash
git clone https://github.com/matrixwhisper/legacy-code-agent.git
cd legacy-code-agent
```

Create a virtual environment:

### Windows

```powershell
python -m venv .venv
.venv\Scripts\activate
```

### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the project dependencies:

```bash
pip install -e .
```

---

# Anthropic API Configuration

The benchmark's agent strategies use the Anthropic API.

Set your API key as an environment variable.

### PowerShell

```powershell
$env:ANTHROPIC_API_KEY="your_api_key_here"
```

### Linux / macOS

```bash
export ANTHROPIC_API_KEY="your_api_key_here"
```

Do not commit API keys or other secrets to Git.

---

# Running the Benchmark

The benchmark harness can be used to execute the COBOL evaluation and agent strategies.

The main components are implemented in:

```text
bench.py
```

and

```text
generate_traj.py
```

To generate agent trajectories:

```bash
python generate_traj.py
```

This runs the configured benchmark tasks using both:

```text
single-shot
iterative
```

strategies.

The resulting trajectories are written to:

```text
trajectories.jsonl
```

and successful training pairs are written to:

```text
sft_data.jsonl
```

---

# Running QLoRA Fine-Tuning

After generating the SFT dataset:

```bash
python finetune.py
```

The script expects:

```text
sft_data.jsonl
```

in the project root.

The trained adapter is saved to:

```text
fine_tuned_adapter/
```

---

# Testing

Run the test suite with:

```bash
pytest
```

The project uses Pytest for automated validation.

You can also run the benchmark tests specifically:

```bash
pytest test_bench.py -v
```

---

# Evaluation Philosophy

The project separates **generation** from **verification**.

An LLM-generated COBOL program is not considered successful simply because:

- it looks correct,
- it contains valid COBOL syntax,
- or the model claims that it fixed the problem.

Instead, the candidate must:

```text
Compile
   ↓
Execute
   ↓
Produce output
   ↓
Match hidden expectations
```

This creates an execution-grounded evaluation loop for legacy code tasks.

---

# Experimentation

The repository also contains:

```text
hillclimb.py
results.jsonl
failure_analysis.md
```

These components provide space for additional experimentation, result collection, optimization, and analysis of unsuccessful agent attempts.

The exact benchmark conclusions should be interpreted from the recorded experiment results rather than assumed from the architecture alone.

---

# Technical Stack

### Core

- Python
- PyTorch
- Pytest

### LLM / AI

- Anthropic Claude
- Qwen2.5-Coder-1.5B-Instruct
- Hugging Face Transformers
- Hugging Face PEFT
- LoRA
- QLoRA

### Model Optimization

- BitsAndBytes
- 4-bit NF4 quantization
- bfloat16
- Gradient accumulation

### Legacy Systems

- COBOL
- GnuCOBOL

### Data

- JSONL
- Hugging Face Datasets
- Generated agent trajectories
- Supervised fine-tuning examples

---

# Current Scope

This repository currently focuses on the experimental workflow:

```text
Legacy COBOL
      ↓
Agent-based code generation
      ↓
Execution-based benchmark
      ↓
Trajectory collection
      ↓
SFT dataset generation
      ↓
QLoRA fine-tuning
```

It is designed as an experimentation and benchmarking project rather than a claim of production deployment.

---

# Future Work

Potential extensions include:

- Expanding the COBOL benchmark with additional tasks.
- Increasing task difficulty and diversity.
- Adding more hidden tests per task.
- Comparing additional agent strategies.
- Evaluating the fine-tuned Qwen model directly against the original model.
- Measuring pass rates before and after fine-tuning.
- Adding structured experiment tracking.
- Improving failure categorization.
- Adding more legacy languages.
- Testing different LoRA configurations.
- Comparing different code-focused foundation models.

---



## Author

**matrixwhisper**

GitHub:  
https://github.com/matrixwhisper

---

<p align="center">
  Built as an experimental project exploring LLM agents, legacy COBOL systems, execution-based evaluation, and parameter-efficient fine-tuning.
</p>