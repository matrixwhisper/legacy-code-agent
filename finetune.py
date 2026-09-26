"""
QLoRA fine-tunes a small Qwen2.5-Coder model on the agent's own generated
trajectories (sft_data.jsonl, produced by generate_traj.py).
"""
import json
import os

import torch
from datasets import Dataset
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainingArguments,
    Trainer,
    DataCollatorForLanguageModeling,
)

BASE_MODEL = "Qwen/Qwen2.5-Coder-1.5B-Instruct"
SFT_DATA_PATH = "sft_data.jsonl"
OUTPUT_DIR = "fine_tuned_adapter"

LORA_RANK = 16
LORA_ALPHA = 32
LORA_DROPOUT = 0.05
TARGET_MODULES = ["q_proj", "k_proj", "v_proj", "o_proj"]

MAX_LENGTH = 2048
NUM_EPOCHS = 3
LEARNING_RATE = 2e-4
BATCH_SIZE = 1
GRAD_ACCUM_STEPS = 8


def load_sft_dataset(path: str) -> Dataset:
    examples = []
    with open(path, "r") as f:
        for line in f:
            row = json.loads(line)
            examples.append({
                "instruction": row["instruction"],
                "response": row["response"],
            })
    return Dataset.from_list(examples)


def format_example(example: dict, tokenizer) -> dict:
    prompt = (
        f"<|im_start|>user\n{example['instruction']}<|im_end|>\n"
        f"<|im_start|>assistant\n{example['response']}<|im_end|>"
    )
    tokenized = tokenizer(
        prompt,
        truncation=True,
        max_length=MAX_LENGTH,
        padding="max_length",
    )
    tokenized["labels"] = tokenized["input_ids"].copy()
    return tokenized


def build_model_and_tokenizer():
    quant_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )

    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        quantization_config=quant_config,
        device_map="auto",
    )
    model = prepare_model_for_kbit_training(model)

    lora_config = LoraConfig(
        r=LORA_RANK,
        lora_alpha=LORA_ALPHA,
        lora_dropout=LORA_DROPOUT,
        target_modules=TARGET_MODULES,
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    return model, tokenizer


def main():
    if not os.path.exists(SFT_DATA_PATH):
        raise FileNotFoundError(
            f"{SFT_DATA_PATH} not found. Run generate_traj.py first to produce training data."
        )

    dataset = load_sft_dataset(SFT_DATA_PATH)
    model, tokenizer = build_model_and_tokenizer()

    tokenized_dataset = dataset.map(
        lambda ex: format_example(ex, tokenizer),
        remove_columns=dataset.column_names,
    )

    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        num_train_epochs=NUM_EPOCHS,
        per_device_train_batch_size=BATCH_SIZE,
        gradient_accumulation_steps=GRAD_ACCUM_STEPS,
        learning_rate=LEARNING_RATE,
        logging_steps=1,
        save_strategy="epoch",
        bf16=True,
        report_to="none",
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_dataset,
        data_collator=DataCollatorForLanguageModeling(tokenizer, mlm=False),
    )

    trainer.train()
    model.save_pretrained(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)
    print(f"Fine-tuned adapter saved to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()