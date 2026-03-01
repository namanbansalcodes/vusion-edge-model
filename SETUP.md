# Complete Setup Guide

This guide will help you set up the Vusion Edge Model demo on your machine.

## Prerequisites

### System Requirements
- **OS:** macOS (M1/M2/M3), Linux, or Windows with WSL
- **RAM:** 8GB minimum, 16GB recommended
- **Storage:** 3GB free space (1GB for model, 2GB for dependencies)
- **Python:** 3.12+ (3.10+ may work)

### Recommended Hardware
- **Apple Silicon:** M1/M2/M3 Mac (uses Metal acceleration)
- **NVIDIA GPU:** CUDA-compatible GPU with 6GB+ VRAM
- **CPU fallback:** Works but slower (~10-15s per inference)

---

## Step 1: Clone the Repository

```bash
git clone https://github.com/namanbansalcodes/vusion-edge-model.git
cd vusion-edge-model
```

---

## Step 2: Set Up Python Environment

### Option A: Using venv (Recommended)
```bash
python3.12 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### Option B: Using conda
```bash
conda create -n vusion python=3.12
conda activate vusion
```

---

## Step 3: Install Dependencies

```bash
# Install core dependencies
pip install -r requirements.txt

# OR install manually
pip install torch>=2.0.0 transformers>=4.30.0 peft>=0.4.0 Pillow>=9.0.0 Django>=6.0.0
```

### Platform-Specific Notes

**macOS (Apple Silicon):**
```bash
# PyTorch with Metal (MPS) support - usually auto-detected
pip install torch torchvision
```

**Linux with CUDA:**
```bash
# Install CUDA-enabled PyTorch
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
```

**Windows:**
```bash
# Use WSL2 for best compatibility
# Or install CUDA version for Windows
```

---

## Step 4: Get the Fine-Tuned Model

The fine-tuned PaliGemma model is **NOT included in git** (too large). You have 3 options:

### Option A: Download from HuggingFace (if available)
```bash
# If the model is uploaded to HuggingFace
huggingface-cli download namanbansalcodes/paligemma-stockout paligemma_stockout_model/
```

### Option B: Copy from Training Machine
```bash
# If you have access to the training machine
scp -r user@training-machine:~/paligemma_stockout_model/ .
```

### Option C: Train Your Own Model
See [Training Guide](#training-your-own-model) below.

### Verify Model Files
After obtaining the model, you should have:
```
paligemma_stockout_model/
├── adapter_config.json
├── adapter_model.safetensors  (~1GB)
└── README.md
```

---

## Step 5: Add Demo Videos

```bash
# Create videos directory (should already exist)
mkdir -p media/videos

# Copy your shelf videos
cp /path/to/your/videos/*.mp4 media/videos/

# OR download sample videos
# (See media/videos/README.md for sources)
```

**Video requirements:**
- Format: MP4 (H.264 codec recommended)
- Resolution: 720p or 1080p
- Duration: 10-60 seconds
- Content: Retail shelves with clear view of products

---

## Step 6: Configure Environment Variables (Optional)

```bash
# Copy the example env file
cp .env.example .env

# Edit .env and add your API keys (only if using Gemini integration)
nano .env
```

**Required for:**
- `GEMINI_API_KEY`: Only needed if integrating Gemini LLM (optional feature)
- `HF_TOKEN`: Only needed for training or downloading gated models

**Not required for basic demo!**

---

## Step 7: Initialize Database

```bash
# Apply migrations
python3.12 manage.py migrate

# Create superuser (optional - for Django admin)
python3.12 manage.py createsuperuser
```

---

## Step 8: Run the Demo

```bash
# Start Django development server
python3.12 manage.py runserver

# Server will start on http://127.0.0.1:8000/
```

### First Launch
- **Model loading:** First request takes 30-40 seconds (one-time)
- **Inference:** Subsequent requests take 2-3 seconds
- **Auto-analysis:** Runs every 2 seconds on video feed

---

## Step 9: Access the Demo

Open your browser and navigate to:
```
http://127.0.0.1:8000/
```

### What You Should See
- ✅ Video feed on the left (auto-playing)
- ✅ Store blueprint on the right with camera markers
- ✅ Processing pipeline below with 3 steps
- ✅ Model status: "Model ready" (green indicator)

### Navigation
- Click camera markers on blueprint to switch feeds
- Use ◀ ▶ buttons or arrow keys
- Auto-analysis runs continuously

---

## Troubleshooting

### Model Not Loading
**Symptom:** "Loading model..." stuck or timeout
**Solution:**
```bash
# Check if model directory exists
ls -la paligemma_stockout_model/

# Verify base model is cached
ls ~/.cache/huggingface/hub/ | grep paligemma

# Check for errors
python3.12 manage.py runserver --noreload
```

### Videos Not Playing
**Symptom:** "No videos" or black screen
**Solution:**
```bash
# Verify videos exist
ls -la media/videos/*.mp4

# Convert to compatible format
ffmpeg -i input.mov -vcodec h264 -acodec aac output.mp4

# Check browser console (F12) for errors
```

### Slow Inference
**Symptom:** Each frame takes >10 seconds
**Solution:**
- First inference is always slower (30-40s)
- Check if GPU is being used:
  - Look for `mps:0` (Mac) or `cuda:0` (NVIDIA) in logs
  - If you see `cpu`, GPU acceleration isn't working
- Reduce video resolution
- Close other applications

### Import Errors
**Symptom:** `ModuleNotFoundError: No module named 'transformers'`
**Solution:**
```bash
# Ensure virtual environment is activated
source .venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

### Port Already in Use
**Symptom:** `Error: That port is already in use.`
**Solution:**
```bash
# Use a different port
python3.12 manage.py runserver 8001

# Or kill the process using port 8000
lsof -ti:8000 | xargs kill -9
```

---

## Training Your Own Model

### Prerequisites
- **GPU:** NVIDIA GPU with 12GB+ VRAM (or use Colab/cloud)
- **Dataset:** COCO-format dataset with annotations
- **HuggingFace Token:** For accessing gated PaliGemma base model

### Steps

1. **Prepare Dataset**
```bash
# Convert COCO dataset to JSONL
python prep_paligemma_dataset.py
```

2. **Set HuggingFace Token**
```bash
export HF_TOKEN=hf_your_token_here
```

3. **Train Locally**
```bash
python finetune_paligemma.py
```

4. **Or Use Remote GPU**
```bash
# On GPU server
python train_server.py
```

**Output:** Fine-tuned model saved to `paligemma_stockout_model/`

---

## Production Deployment

### Edge Device Deployment
```bash
# Raspberry Pi / Jetson Nano
# (Requires PyTorch for ARM)
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

### Optimize for Production
```bash
# Enable quantization (optional)
pip install bitsandbytes

# Use environment variables
export DJANGO_SETTINGS_MODULE=stockout_demo.settings
export DEBUG=False
```

### Run with Gunicorn
```bash
pip install gunicorn
gunicorn stockout_demo.wsgi:application --bind 0.0.0.0:8000
```

---

## Verification Checklist

Before running the demo, verify:

- [ ] Python 3.12+ installed
- [ ] Dependencies installed (`pip list | grep torch`)
- [ ] Model directory exists (`ls paligemma_stockout_model/`)
- [ ] Videos in place (`ls media/videos/*.mp4`)
- [ ] Migrations applied (`python manage.py showmigrations`)
- [ ] Server starts without errors
- [ ] Can access http://127.0.0.1:8000/
- [ ] Model status shows "ready"
- [ ] Video plays automatically
- [ ] Analysis runs every 2 seconds

---

## Next Steps

Once the demo is running:

1. **Test different videos** - Add more videos to `media/videos/`
2. **Integrate Gemini** - Set `GEMINI_API_KEY` for LLM reasoning
3. **Customize UI** - Edit `static/css/style.css`
4. **Add function calling** - Implement alerts/inventory updates
5. **Deploy to edge** - Test on Raspberry Pi or Jetson

---

## Getting Help

**Check Logs:**
```bash
# Django server logs (in terminal)
# Browser console (F12 → Console tab)
# Model loading logs (first request)
```

**Common Issues:**
- Model loading: See troubleshooting above
- Video playback: Check codec (H.264 works best)
- Slow inference: Verify GPU usage
- Import errors: Reinstall dependencies

**Resources:**
- Main README: [README.md](README.md)
- Demo Docs: [DEMO_README.md](DEMO_README.md)
- Project Log: [PROJECT_LOG.md](PROJECT_LOG.md)

---

**Ready to detect stock-outs!** 🚀
