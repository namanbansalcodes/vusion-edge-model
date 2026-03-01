"""
Persistent training server — keeps model in GPU memory.
Load once, then re-run training/eval/inference without reloading.

Usage on VM:
  HF_TOKEN=hf_xxx python3 train_server.py

Commands (type at prompt):
  train [epochs]  — run training (default 5 epochs)
  eval            — evaluate on val set
  infer <img>     — run inference on an image
  reload          — reload dataset from disk
  quit            — exit
"""

import json
import os
import random
import torch
from PIL import Image
from torch.utils.data import Dataset, DataLoader
from transformers import PaliGemmaForConditionalGeneration, PaliGemmaProcessor
from peft import get_peft_model, LoraConfig

# ── Config ──────────────────────────────────────────────────────────────
MODEL_ID = "google/paligemma-3b-pt-224"
DATASET_DIR = "paligemma_dataset"
JSONL_PATH = os.path.join(DATASET_DIR, "dataset.jsonl")
IMG_DIR = os.path.join(DATASET_DIR, "images")
OUTPUT_DIR = "paligemma_stockout_model"

BATCH_SIZE = 4
LR = 2e-4
MAX_LENGTH = 512
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
VAL_SPLIT = 0.15
SEED = 42

ALL_ZONES = [
    "top-left",
    "top-center",
    "top-right",
    "middle-left",
    "middle-center",
    "middle-right",
    "bottom-left",
    "bottom-center",
    "bottom-right",
]


class StockOutDataset(Dataset):
    def __init__(self, samples, img_dir, processor):
        self.processor = processor
        self.img_dir = img_dir
        self.samples = samples

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        sample = self.samples[idx]
        image = Image.open(os.path.join(self.img_dir, sample["image"])).convert("RGB")
        prompt = sample["prompt"]
        answer = sample["response"]

        inputs = self.processor(
            text=prompt,
            suffix=answer,
            images=image,
            return_tensors="pt",
            padding="max_length",
            max_length=MAX_LENGTH,
        )

        input_ids = inputs["input_ids"].squeeze(0)
        attention_mask = inputs["attention_mask"].squeeze(0)
        pixel_values = inputs["pixel_values"].squeeze(0)
        token_type_ids = inputs["token_type_ids"].squeeze(0)

        labels = input_ids.clone()
        labels[token_type_ids == 0] = -100
        labels[attention_mask == 0] = -100

        return {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "pixel_values": pixel_values,
            "token_type_ids": token_type_ids,
            "labels": labels,
        }


def load_data():
    with open(JSONL_PATH) as f:
        all_samples = [json.loads(line) for line in f]
    random.seed(SEED)
    random.shuffle(all_samples)
    split_idx = int(len(all_samples) * (1 - VAL_SPLIT))
    train_samples = all_samples[:split_idx]
    val_samples = all_samples[split_idx:]
    print(
        f"Dataset: {len(all_samples)} total -> {len(train_samples)} train, {len(val_samples)} val"
    )
    return train_samples, val_samples


def do_train(model, processor, train_samples, epochs=5, lr=LR):
    dataset = StockOutDataset(train_samples, IMG_DIR, processor)
    loader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True)

    optimizer = torch.optim.AdamW(
        [p for p in model.parameters() if p.requires_grad], lr=lr, weight_decay=0.01
    )
    total_steps = epochs * len(loader)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=total_steps)

    model.train()
    for epoch in range(epochs):
        total_loss = 0
        for step, batch in enumerate(loader):
            batch = {k: v.to(DEVICE) for k, v in batch.items()}
            outputs = model(**batch)
            loss = outputs.loss

            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            scheduler.step()
            optimizer.zero_grad()

            total_loss += loss.item()
            if step % 10 == 0:
                lr_now = scheduler.get_last_lr()[0]
                print(
                    f"  Epoch {epoch+1}/{epochs} | Step {step}/{len(loader)} | Loss: {loss.item():.4f} | LR: {lr_now:.2e}"
                )

        avg = total_loss / len(loader)
        print(f"Epoch {epoch+1}/{epochs} done -- avg loss: {avg:.4f}")

    print("Training done.")


def do_eval(model, processor, val_samples):
    model.eval()
    tp, fp, fn = 0, 0, 0
    exact_match = 0
    total = 0

    for i, sample in enumerate(val_samples):
        image = Image.open(os.path.join(IMG_DIR, sample["image"])).convert("RGB")
        inputs = processor(
            text="detect stock out", images=image, return_tensors="pt"
        ).to(DEVICE)

        with torch.no_grad():
            output = model.generate(**inputs, max_new_tokens=128)
        decoded = processor.decode(output[0], skip_special_tokens=True)

        pred_zones = set(z for z in ALL_ZONES if z in decoded)
        gt_zones = set(sample["zones"])

        tp += len(pred_zones & gt_zones)
        fp += len(pred_zones - gt_zones)
        fn += len(gt_zones - pred_zones)

        if pred_zones == gt_zones:
            exact_match += 1
        total += 1

        if i < 5:
            print(f"  [{i+1}] Expected: {sample['response']}")
            print(f"       Got:      {decoded}")

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = (
        2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    )
    em_rate = exact_match / total if total > 0 else 0

    print(f"\n{'='*50}")
    print(f"EVALUATION ({total} val samples)")
    print(f"{'='*50}")
    print(f"Precision: {precision:.3f}")
    print(f"Recall:    {recall:.3f}")
    print(f"F1:        {f1:.3f}")
    print(f"Exact Match: {em_rate:.3f} ({exact_match}/{total})")
    print(f"{'='*50}")


def do_infer(model, processor, img_path):
    model.eval()
    image = Image.open(img_path).convert("RGB")
    inputs = processor(text="detect stock out", images=image, return_tensors="pt").to(
        DEVICE
    )
    with torch.no_grad():
        output = model.generate(**inputs, max_new_tokens=128)
    decoded = processor.decode(output[0], skip_special_tokens=True)
    detected = [z for z in ALL_ZONES if z in decoded]
    print(f"Raw: {decoded}")
    print(f"Zones: {', '.join(detected) if detected else 'none'}")


def save_model(model, processor):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    model.save_pretrained(OUTPUT_DIR)
    processor.save_pretrained(OUTPUT_DIR)
    print(f"Saved to {OUTPUT_DIR}")


def main():
    print(f"Device: {DEVICE}")
    print("Loading model (one-time)...")

    processor = PaliGemmaProcessor.from_pretrained(MODEL_ID)
    model = PaliGemmaForConditionalGeneration.from_pretrained(
        MODEL_ID,
        torch_dtype=torch.bfloat16,
    )

    lora_config = LoraConfig(
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        modules_to_save=["lm_head"],
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()
    model.to(DEVICE)

    train_samples, val_samples = load_data()

    print(
        "\nModel loaded and ready! Commands: train [epochs] [lr], eval, infer <img>, save, reload, quit"
    )

    while True:
        try:
            cmd = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not cmd:
            continue

        parts = cmd.split()
        action = parts[0].lower()

        if action == "quit" or action == "exit":
            break
        elif action == "train":
            epochs = int(parts[1]) if len(parts) > 1 else 5
            lr = float(parts[2]) if len(parts) > 2 else LR
            do_train(model, processor, train_samples, epochs=epochs, lr=lr)
        elif action == "eval":
            do_eval(model, processor, val_samples)
        elif action == "infer":
            if len(parts) < 2:
                print("Usage: infer <image_path>")
            else:
                do_infer(model, processor, parts[1])
        elif action == "save":
            save_model(model, processor)
        elif action == "reload":
            train_samples, val_samples = load_data()
        else:
            print("Unknown command. Use: train, eval, infer, save, reload, quit")

    print("Bye!")


if __name__ == "__main__":
    main()
