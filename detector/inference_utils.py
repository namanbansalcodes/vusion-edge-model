"""
Utilities for running PaliGemma inference in Django
Wraps the quick_finetuned_inference.py logic
"""
import torch
from transformers import PaliGemmaForConditionalGeneration, PaliGemmaProcessor
from peft import PeftModel
from pathlib import Path

# Model paths
BASE_MODEL_ID = "google/paligemma-3b-pt-224"
BASE_DIR = Path(__file__).resolve().parent.parent
ADAPTER_DIR = BASE_DIR / "paligemma_stockout_model"

# Zone definitions
ALL_ZONES = [
    "top-left", "top-center", "top-right",
    "middle-left", "middle-center", "middle-right",
    "bottom-left", "bottom-center", "bottom-right",
]

# Global model cache (load once, reuse)
_model = None
_processor = None
_model_loaded = False


def load_model():
    """Load PaliGemma model (cached globally)"""
    global _model, _processor, _model_loaded

    if _model_loaded:
        return _model, _processor

    print("Loading fine-tuned PaliGemma model...")

    # Load processor
    _processor = PaliGemmaProcessor.from_pretrained(str(ADAPTER_DIR))

    # Load base model
    print("  Loading base model...")
    base_model = PaliGemmaForConditionalGeneration.from_pretrained(
        BASE_MODEL_ID,
        torch_dtype=torch.float16,
        device_map="mps" if torch.backends.mps.is_available() else "auto",
        low_cpu_mem_usage=True
    )

    # Load fine-tuned adapter
    print("  Loading LoRA adapter...")
    _model = PeftModel.from_pretrained(base_model, str(ADAPTER_DIR))
    _model.eval()

    _model_loaded = True
    print(f"✓ Model loaded on {_model.device}")

    return _model, _processor


def is_model_loaded():
    """Check if model is loaded"""
    return _model_loaded


def detect_stockouts(image, prompt="detect stock out"):
    """
    Run stock-out detection on a single image

    Args:
        image: PIL Image
        prompt: Text prompt (default: "detect stock out")

    Returns:
        dict with keys:
            - raw_output: Full model output
            - detected_zones: List of detected zone names
            - commentary: General shelf observations
    """
    # Load model if not already loaded
    model, processor = load_model()

    # === DETECTION: Check for stock-outs ===
    inputs = processor(text=prompt, images=image, return_tensors="pt")
    inputs = {k: v.to(model.device) for k, v in inputs.items()}

    with torch.no_grad():
        outputs = model.generate(**inputs, max_new_tokens=128)

    detection_output = processor.decode(outputs[0], skip_special_tokens=True)

    # Parse detected zones (more conservative - only if explicitly mentioned)
    detected_zones = []
    output_lower = detection_output.lower()
    for zone in ALL_ZONES:
        # Only count if zone is clearly mentioned with context
        if zone in output_lower and ("stock" in output_lower or "empty" in output_lower):
            detected_zones.append(zone)

    # === COMMENTARY: General shelf observations ===
    commentary_prompt = "describe the shelf condition and organization"
    commentary_inputs = processor(text=commentary_prompt, images=image, return_tensors="pt")
    commentary_inputs = {k: v.to(model.device) for k, v in commentary_inputs.items()}

    with torch.no_grad():
        commentary_outputs = model.generate(**commentary_inputs, max_new_tokens=100)

    commentary = processor.decode(commentary_outputs[0], skip_special_tokens=True)

    # Generate human-readable commentary
    shelf_comments = []
    commentary_lower = commentary.lower()

    # Check for tidiness
    if any(word in commentary_lower for word in ['tidy', 'organized', 'neat', 'well-arranged']):
        shelf_comments.append("Shelf is well-organized")
    elif any(word in commentary_lower for word in ['messy', 'disorganized', 'cluttered']):
        shelf_comments.append("Shelf appears disorganized")

    # Check for falling items
    if any(word in commentary_lower for word in ['falling', 'tipping', 'leaning', 'unstable']):
        shelf_comments.append("Some items may be unstable")

    # Check for fullness
    if any(word in commentary_lower for word in ['full', 'stocked', 'plenty']):
        shelf_comments.append("Shelf is well-stocked")
    elif any(word in commentary_lower for word in ['sparse', 'few', 'limited']):
        shelf_comments.append("Low stock levels observed")

    # Default if no specific observations
    if not shelf_comments:
        shelf_comments.append("Shelf condition appears normal")

    return {
        'raw_output': detection_output,
        'detected_zones': detected_zones,
        'commentary': ' • '.join(shelf_comments),
        'commentary_raw': commentary
    }
