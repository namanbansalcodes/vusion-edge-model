# PaliGemma Stock-Out Detection

Fine-tuned PaliGemma 3B model for detecting empty zones on retail shelves using a 3x3 grid system.

## 🎯 Project Overview

This project fine-tunes Google's PaliGemma 3B vision-language model to detect stock-outs on retail shelves. Instead of traditional bounding boxes, the model outputs zone-based predictions using a 3x3 grid (top-left, top-center, top-right, middle-left, etc.).

**Model Performance (Run 3):**
- F1 Score: 0.601
- Precision: 0.481
- Recall: 0.801

## 🚀 Quick Start - Running the Model (FINALIZED METHOD)

### Prerequisites

- Python 3.12
- M3 Mac (or any device with MPS/CUDA/CPU)
- ~6GB free memory for model

### Installation

```bash
# Install dependencies
pip install torch transformers peft pillow
```

### Run Inference with Fine-Tuned Model

**This is the recommended and finalized method:**

```bash
python3.12 quick_finetuned_inference.py [image_path]
```

**Examples:**

```bash
# Use default test image
python3.12 quick_finetuned_inference.py

# Use your own image
python3.12 quick_finetuned_inference.py path/to/shelf_image.jpg

# Custom prompt (optional)
python3.12 quick_finetuned_inference.py image.jpg "detect stock out"
```

**Expected Output:**
```
Loading fine-tuned model...
  Loading base model...
  Loading LoRA adapter...
✓ Fine-tuned model loaded on mps:0
✓ Image loaded: (2272, 1704)
Generating response for: 'detect stock out'...

🤖 Raw output: detect stock out
📍 Detected stock-out zones: top-left, top-center, middle-left, middle-center, bottom-left, bottom-center
```

### Performance Notes

- **First run**: ~30-40 seconds (loading model weights)
- **Inference**: ~2-3 seconds per image
- **Memory**: ~5-6GB GPU/unified memory
- **Device**: Runs on M3 Metal GPU (MPS), CUDA, or CPU

## 📁 Project Structure

```
bifrost/
├── quick_finetuned_inference.py    # ⭐ MAIN: Run fine-tuned model inference
├── quick_inference.py              # Run base PaliGemma model
├── quick_test.py                   # Alternative test script
├── finetune_paligemma.py          # Training script (LoRA fine-tuning)
├── train_server.py                # Remote GPU training server
├── prep_paligemma_dataset.py      # Dataset preparation (COCO → JSONL)
├── paligemma_stockout_model/      # Fine-tuned LoRA adapter (~1GB)
└── paligemma_dataset/             # Training images + JSONL labels
```

## 🏋️ Model Details

**Base Model:** `google/paligemma-3b-pt-224`
- 3 billion parameters
- 224x224 image resolution
- PyTorch format

**Fine-Tuning Method:** LoRA (Low-Rank Adaptation)
- Adapter size: ~1GB (vs 5.4GB full model)
- Trainable params: ~16M
- Target modules: q_proj, k_proj, v_proj, o_proj
- LoRA rank: 16, alpha: 32

**Output Format:** Natural language zone labels
```
Zones: top-left, top-center, top-right,
       middle-left, middle-center, middle-right,
       bottom-left, bottom-center, bottom-right
```

## 🔧 Training (Optional)

If you want to retrain the model:

```bash
# Prepare dataset from COCO format
python prep_paligemma_dataset.py

# Fine-tune locally (requires GPU)
HF_TOKEN=your_token python finetune_paligemma.py

# Or use remote GPU server
python train_server.py
```

## 📊 Dataset

- **Source**: COCO-format shelf images
- **Size**: 299 images
- **Format**: JSONL with zone annotations
- **Split**: 85% train, 15% validation

## 🛠️ Technical Stack

- **Framework**: HuggingFace Transformers + PEFT
- **Backend**: PyTorch with Metal Performance Shaders (MPS)
- **Training**: LoRA fine-tuning on RTX A6000 GPU
- **Inference**: On-device (M3 MacBook Air)

## 🔒 Privacy

✅ **100% on-device inference** - no cloud APIs
✅ **No data leaves your machine**
✅ **No API keys required for inference**

## 📝 License

Model weights based on Google's PaliGemma (Apache 2.0 compatible).

---

**Built with Claude Code** 🤖
