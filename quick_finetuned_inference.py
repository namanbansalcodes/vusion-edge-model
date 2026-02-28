#!/usr/bin/env python3
"""
Fast local inference with fine-tuned PaliGemma stock-out model on M3
Usage: python3.12 quick_finetuned_inference.py [image_path] [prompt]
"""
import torch
from transformers import PaliGemmaForConditionalGeneration, PaliGemmaProcessor
from peft import PeftModel
from PIL import Image
import sys

# Model paths
BASE_MODEL_ID = "google/paligemma-3b-pt-224"
ADAPTER_DIR = "paligemma_stockout_model"

# Zone definitions
ALL_ZONES = [
    "top-left", "top-center", "top-right",
    "middle-left", "middle-center", "middle-right",
    "bottom-left", "bottom-center", "bottom-right",
]

def run_inference(image_path, prompt="detect stock out"):
    print("Loading fine-tuned model...")

    # Load processor from adapter directory
    processor = PaliGemmaProcessor.from_pretrained(ADAPTER_DIR)

    # Load base model
    print("  Loading base model...")
    base_model = PaliGemmaForConditionalGeneration.from_pretrained(
        BASE_MODEL_ID,
        torch_dtype=torch.float16,
        device_map="mps",  # Apple Metal for M3
        low_cpu_mem_usage=True
    )

    # Load fine-tuned adapter
    print("  Loading LoRA adapter...")
    model = PeftModel.from_pretrained(base_model, ADAPTER_DIR)
    model.eval()

    print(f"✓ Fine-tuned model loaded on {model.device}")

    # Load image
    image = Image.open(image_path).convert("RGB")
    print(f"✓ Image loaded: {image.size}")

    # Process
    inputs = processor(text=prompt, images=image, return_tensors="pt")
    inputs = {k: v.to(model.device) for k, v in inputs.items()}

    # Generate
    print(f"Generating response for: '{prompt}'...")
    with torch.no_grad():
        outputs = model.generate(**inputs, max_new_tokens=128)

    result = processor.decode(outputs[0], skip_special_tokens=True)
    print(f"\n🤖 Raw output: {result}")

    # Parse detected zones
    detected = [zone for zone in ALL_ZONES if zone in result]
    if detected:
        print(f"📍 Detected stock-out zones: {', '.join(detected)}")
    else:
        print("📍 No stock-out zones detected")

    return result

if __name__ == "__main__":
    if len(sys.argv) < 2:
        # Use a test image
        test_image = "paligemma_dataset/images/00d4450e-2571-4055-906f-d9236333fc0b_jpg.rf.Xeuw6FUd8ZmXLxT78ibW.jpg"
        prompt = "detect stock out"
        print(f"Using test image: {test_image}")
    else:
        test_image = sys.argv[1]
        prompt = sys.argv[2] if len(sys.argv) > 2 else "detect stock out"

    run_inference(test_image, prompt)
