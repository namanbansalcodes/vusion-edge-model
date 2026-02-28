"""
Quick test of local PaliGemma inference with progress messages.
"""

import torch
from PIL import Image
from transformers import PaliGemmaForConditionalGeneration, PaliGemmaProcessor
from peft import PeftModel

print("=" * 60)
print("PaliGemma Stock-Out Detection - Quick Test")
print("=" * 60)

# Auto-detect device
if torch.cuda.is_available():
    DEVICE = "cuda"
    DTYPE = torch.bfloat16
elif torch.backends.mps.is_available():
    DEVICE = "mps"
    DTYPE = torch.float32
else:
    DEVICE = "cpu"
    DTYPE = torch.float32

print(f"\n✓ Device: {DEVICE}")

# Load model
print("\n[1/4] Loading processor...")
processor = PaliGemmaProcessor.from_pretrained("paligemma_stockout_model")

print("[2/4] Loading base model...")
base_model = PaliGemmaForConditionalGeneration.from_pretrained(
    "google/paligemma-3b-pt-224",
    torch_dtype=DTYPE,
)

print("[3/4] Loading LoRA adapter...")
model = PeftModel.from_pretrained(base_model, "paligemma_stockout_model")
model.to(DEVICE)
model.eval()

print("[4/4] Running inference...")

# Test image
import sys
img_path = sys.argv[1] if len(sys.argv) > 1 else "paligemma_dataset/images/00d4450e-2571-4055-906f-d9236333fc0b_jpg.rf.Xeuw6FUd8ZmXLxT78ibW.jpg"
image = Image.open(img_path).convert("RGB")
inputs = processor(text="detect stock out", images=image, return_tensors="pt").to(DEVICE)

with torch.no_grad():
    output = model.generate(**inputs, max_new_tokens=128)

decoded = processor.decode(output[0], skip_special_tokens=True)

# Display results
ALL_ZONES = [
    "top-left", "top-center", "top-right",
    "middle-left", "middle-center", "middle-right",
    "bottom-left", "bottom-center", "bottom-right",
]
detected = [z for z in ALL_ZONES if z in decoded]

print("\n" + "=" * 60)
print("RESULTS")
print("=" * 60)
print(f"Image: {img_path.split('/')[-1][:50]}...")
print(f"\nRaw output:\n  {decoded}")
print(f"\nDetected zones ({len(detected)}):")
for zone in detected:
    print(f"  ✓ {zone}")
if not detected:
    print("  (none)")
print("=" * 60)
print("\n✓ Test complete!")
