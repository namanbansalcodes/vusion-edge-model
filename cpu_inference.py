"""
Simple CPU-only inference - no MPS compilation delays.
Takes ~10-30 seconds per image but works immediately.
"""

import torch
from PIL import Image
from transformers import PaliGemmaForConditionalGeneration, PaliGemmaProcessor
from peft import PeftModel
import sys

# Force CPU - no MPS compilation
torch.set_num_threads(8)  # Use all CPU cores

print("=" * 60)
print("PaliGemma CPU Inference (No GPU)")
print("=" * 60)
print("\n✓ Using CPU with 8 threads")

# Load
print("\n[1/3] Loading processor...")
processor = PaliGemmaProcessor.from_pretrained("paligemma_stockout_model")

print("[2/3] Loading base model (CPU)...")
base_model = PaliGemmaForConditionalGeneration.from_pretrained(
    "google/paligemma-3b-pt-224",
    torch_dtype=torch.float32,
    low_cpu_mem_usage=True,
)

print("[3/3] Loading LoRA adapter...")
model = PeftModel.from_pretrained(base_model, "paligemma_stockout_model")
model.eval()

# Get image
img_path = (
    sys.argv[1]
    if len(sys.argv) > 1
    else "paligemma_dataset/images/00d4450e-2571-4055-906f-d9236333fc0b_jpg.rf.Xeuw6FUd8ZmXLxT78ibW.jpg"
)

print(f"\n[Running] {img_path.split('/')[-1][:50]}...")
image = Image.open(img_path).convert("RGB")
# Note: The processor warning is harmless - it auto-adds image tokens
inputs = processor(text="detect stock out", images=image, return_tensors="pt")

with torch.no_grad():
    output = model.generate(**inputs, max_new_tokens=128)

decoded = processor.decode(output[0], skip_special_tokens=True)

# Parse
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
detected = [z for z in ALL_ZONES if z in decoded]

print("\n" + "=" * 60)
print("RESULTS")
print("=" * 60)
print(f"\nRaw: {decoded}")
print(f"\nZones ({len(detected)}):")
for zone in detected:
    print(f"  ✓ {zone}")
print("=" * 60)
