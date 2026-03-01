# Fine-Tuned PaliGemma Model

This directory should contain the fine-tuned LoRA adapter for PaliGemma 3B.

## ⚠️ Model Not Included in Git

The model files are **excluded from the repository** because they're too large (~1GB).

## Required Files

You need these files in this directory:

```
paligemma_stockout_model/
├── adapter_config.json       # LoRA configuration
├── adapter_model.safetensors # LoRA weights (~1GB)
└── README.md                 # This file
```

---

## How to Get the Model

### Option 1: Download from HuggingFace

If the model has been uploaded to HuggingFace:

```bash
# From project root
huggingface-cli download namanbansalcodes/paligemma-stockout paligemma_stockout_model/
```

### Option 2: Copy from Training Machine

```bash
# From your local machine
scp -r user@training-machine:~/vusion-edge-model/paligemma_stockout_model/ .

# Example with specific IP
scp -r hackathon@34.29.42.58:~/paligemma_stockout_model/ .
```

### Option 3: Train Your Own

See the main [SETUP.md](../SETUP.md) for training instructions.

---

## Verification

After obtaining the model, verify the files:

```bash
ls -lh paligemma_stockout_model/
# Should see adapter_config.json and adapter_model.safetensors (~1GB)
```

---

**Without these model files, the demo will not work!**
