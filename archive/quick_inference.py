#!/usr/bin/env python3
"""
Fast PaliGemma base model inference on M3
Usage: python3.12 quick_inference.py [image_path] [prompt]
"""
import torch
from transformers import PaliGemmaForConditionalGeneration, PaliGemmaProcessor
from PIL import Image
import sys

MODEL_ID = "google/paligemma-3b-pt-224"


def run_inference(image_path, prompt="describe this image"):
    print("Loading base model from cache...")

    processor = PaliGemmaProcessor.from_pretrained(MODEL_ID)
    model = PaliGemmaForConditionalGeneration.from_pretrained(
        MODEL_ID,
        torch_dtype=torch.float16,
        device_map="mps",  # KEY: Load directly to Metal GPU
        low_cpu_mem_usage=True,
    )

    print(f"✓ Model loaded on {model.device}")

    # Load image
    image = Image.open(image_path).convert("RGB")
    print(f"✓ Image loaded: {image.size}")

    # Process
    inputs = processor(text=prompt, images=image, return_tensors="pt")
    inputs = {k: v.to(model.device) for k, v in inputs.items()}

    # Generate
    print(f"Generating response for: '{prompt}'...")
    with torch.no_grad():
        outputs = model.generate(**inputs, max_new_tokens=100)

    result = processor.decode(outputs[0], skip_special_tokens=True)
    print(f"\n🤖 {result}\n")
    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        test_image = "paligemma_dataset/images/00d4450e-2571-4055-906f-d9236333fc0b_jpg.rf.Xeuw6FUd8ZmXLxT78ibW.jpg"
        prompt = "describe this image"
        print(f"Using test image: {test_image}")
    else:
        test_image = sys.argv[1]
        prompt = sys.argv[2] if len(sys.argv) > 2 else "describe this image"

    run_inference(test_image, prompt)
