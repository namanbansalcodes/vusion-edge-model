"""
PaliGemma fine-tuning for stock-out zone detection.
Uses HuggingFace transformers + LoRA via PEFT. PyTorch backend.

Key fix: uses processor's `suffix` param for proper prompt/answer separation,
and token_type_ids for label masking (0=prompt/image, 1=answer).

Usage: HF_TOKEN=hf_xxx python finetune_paligemma.py
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

EPOCHS = 5
BATCH_SIZE = 4
LR = 2e-4
MAX_LENGTH = 512
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
VAL_SPLIT = 0.15
SEED = 42


# ── Dataset ─────────────────────────────────────────────────────────────
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

        # Use suffix= so the processor properly separates prompt from answer
        # This sets token_type_ids: 0 for image+prompt tokens, 1 for answer tokens
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

        # Labels: only compute loss on the answer portion (token_type_ids == 1)
        labels = input_ids.clone()
        labels[token_type_ids == 0] = -100  # mask prompt + image tokens
        labels[attention_mask == 0] = -100   # mask padding

        return {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "pixel_values": pixel_values,
            "token_type_ids": token_type_ids,
            "labels": labels,
        }


def load_and_split(jsonl_path):
    """Load JSONL and split into train/val."""
    with open(jsonl_path) as f:
        all_samples = [json.loads(line) for line in f]

    random.seed(SEED)
    random.shuffle(all_samples)
    split_idx = int(len(all_samples) * (1 - VAL_SPLIT))
    train_samples = all_samples[:split_idx]
    val_samples = all_samples[split_idx:]
    print(f"Dataset: {len(all_samples)} total → {len(train_samples)} train, {len(val_samples)} val")
    return train_samples, val_samples


def evaluate(model, processor, val_samples, img_dir):
    """Evaluate on val set: zone-level precision/recall/F1 + exact match."""
    model.eval()
    all_zones = [
        "top-left", "top-center", "top-right",
        "middle-left", "middle-center", "middle-right",
        "bottom-left", "bottom-center", "bottom-right",
    ]

    tp, fp, fn = 0, 0, 0
    exact_match = 0
    total = 0

    for sample in val_samples:
        image = Image.open(os.path.join(img_dir, sample["image"])).convert("RGB")
        inputs = processor(text="detect stock out", images=image, return_tensors="pt").to(DEVICE)

        with torch.no_grad():
            output = model.generate(**inputs, max_new_tokens=128)

        decoded = processor.decode(output[0], skip_special_tokens=True)

        # Parse predicted zones from model output
        pred_zones = set()
        for zone in all_zones:
            if zone in decoded:
                pred_zones.add(zone)

        # Ground truth zones
        gt_zones = set(sample["zones"])

        # Zone-level metrics
        tp += len(pred_zones & gt_zones)
        fp += len(pred_zones - gt_zones)
        fn += len(gt_zones - pred_zones)

        if pred_zones == gt_zones:
            exact_match += 1
        total += 1

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    em_rate = exact_match / total if total > 0 else 0

    print(f"\n{'='*50}")
    print(f"EVALUATION ({total} val samples)")
    print(f"{'='*50}")
    print(f"Zone-level Precision: {precision:.3f}")
    print(f"Zone-level Recall:    {recall:.3f}")
    print(f"Zone-level F1:        {f1:.3f}")
    print(f"Exact Match Rate:     {em_rate:.3f} ({exact_match}/{total})")
    print(f"{'='*50}")

    return {"precision": precision, "recall": recall, "f1": f1, "exact_match": em_rate}


# ── Main ────────────────────────────────────────────────────────────────
def main():
    print(f"Device: {DEVICE}")
    print(f"Loading model: {MODEL_ID}")

    processor = PaliGemmaProcessor.from_pretrained(MODEL_ID)
    model = PaliGemmaForConditionalGeneration.from_pretrained(
        MODEL_ID,
        torch_dtype=torch.bfloat16,
    )

    # LoRA — target language model attention for generation quality
    # PEFT automatically freezes all base params; only LoRA adapters are trainable
    # Use modules_to_save to also train the lm_head for better text generation
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

    # Dataset split
    train_samples, val_samples = load_and_split(JSONL_PATH)
    train_dataset = StockOutDataset(train_samples, IMG_DIR, processor)
    train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True)

    # Optimizer + scheduler
    optimizer = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=0.01)
    total_steps = EPOCHS * len(train_loader)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=total_steps)

    # ── Training loop ───────────────────────────────────────────────────
    model.train()
    for epoch in range(EPOCHS):
        total_loss = 0
        for step, batch in enumerate(train_loader):
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
                lr = scheduler.get_last_lr()[0]
                print(f"  Epoch {epoch+1}/{EPOCHS} | Step {step}/{len(train_loader)} | Loss: {loss.item():.4f} | LR: {lr:.2e}")

        avg_loss = total_loss / len(train_loader)
        print(f"Epoch {epoch+1}/{EPOCHS} done — avg loss: {avg_loss:.4f}")

    # ── Save ────────────────────────────────────────────────────────────
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    model.save_pretrained(OUTPUT_DIR)
    processor.save_pretrained(OUTPUT_DIR)
    print(f"\nModel saved to {OUTPUT_DIR}")

    # ── Evaluation on val set ────────────────────────────────────────────
    evaluate(model, processor, val_samples, IMG_DIR)

    # ── Sample predictions ───────────────────────────────────────────────
    print("\n--- Sample Predictions (first 5 val) ---")
    model.eval()
    for i, sample in enumerate(val_samples[:5]):
        image = Image.open(os.path.join(IMG_DIR, sample["image"])).convert("RGB")
        inputs = processor(text="detect stock out", images=image, return_tensors="pt").to(DEVICE)
        with torch.no_grad():
            output = model.generate(**inputs, max_new_tokens=128)
        decoded = processor.decode(output[0], skip_special_tokens=True)
        print(f"\n[{i+1}] Expected: {sample['response']}")
        print(f"    Got:      {decoded}")


if __name__ == "__main__":
    main()
