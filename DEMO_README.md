# Stock-Out Detection Demo - Django Web App

Interactive demo showcasing on-device stock-out detection using PaliGemma + Gemma.

## 🎯 Demo Purpose

**The Problem:** Stock-outs cost retailers billions annually. Manual detection is slow and error-prone.

**Our Solution:** On-device AI that:
- Detects stock-outs in real-time from shelf cameras
- Runs 100% on-device (GDPR-compliant, no data leaves the device)
- Uses PaliGemma 3B for zone-based detection
- Integrates with Gemma for intelligent tool calling

## 🚀 Quick Start

### 1. Prerequisites

```bash
# Python 3.12
# Dependencies from main project (transformers, torch, peft)
```

### 2. Install Django

```bash
pip install django pillow
```

### 3. Add Demo Videos

Place your shelf videos in `static/videos/`:

```bash
mkdir -p static/videos
# Copy your demo video as shelf_demo.mp4
cp /path/to/your/video.mp4 static/videos/shelf_demo.mp4
```

### 4. Run the Demo

```bash
# Run migrations (first time only)
python3.12 manage.py migrate

# Start the server
python3.12 manage.py runserver
```

### 5. Open in Browser

```
http://127.0.0.1:8000/
```

## 🏗️ Architecture

### ML Pipeline

```
📹 Video Feed (Shelf Camera)
    ↓
🔍 PaliGemma 3B (Stock-out Detection)
    ↓ (if stock-out detected)
💬 Gemma (LLM Reasoning) [Teammate's Integration]
    ↓
⚡ Function Calls (Actions/Alerts)
```

### UI Layout

- **Top**: Video player with shelf camera feed (looping demo video)
- **Bottom**: ML workflow visualization
  - Step 1: PaliGemma (with icon, logs, detected zones)
  - Step 2: Gemma LLM (placeholder for teammate's integration)
  - Step 3: Function Calls (tool calling results)

## 📁 Project Structure

```
bifrost/
├── stockout_demo/          # Django project
│   ├── settings.py
│   └── urls.py
├── detector/               # Main app
│   ├── views.py           # API endpoints
│   ├── inference_utils.py  # PaliGemma wrapper
│   ├── templates/
│   │   └── detector/
│   │       └── index.html  # Main UI
│   └── urls.py
├── static/
│   ├── css/
│   │   └── style.css      # Sleek gradient UI
│   ├── js/
│   │   └── app.js         # Frontend logic
│   └── videos/
│       └── shelf_demo.mp4  # Demo video (user-provided)
├── paligemma_stockout_model/  # Fine-tuned LoRA adapter
└── manage.py
```

## 🔌 API Endpoints

### `GET /api/model-status/`
Check if PaliGemma model is loaded.

**Response:**
```json
{
  "loaded": true,
  "status": "ready"
}
```

### `POST /api/process-frame/`
Analyze a video frame for stock-outs.

**Request:**
```json
{
  "image": "data:image/jpeg;base64,..."
}
```

**Response:**
```json
{
  "success": true,
  "steps": {
    "paligemma": {
      "status": "complete",
      "detected_zones": ["top-left", "middle-center"],
      "logs": ["Analyzed frame", "Detected 2 stock-out zones"]
    },
    "gemma": {
      "status": "pending",
      "enabled": true,
      "logs": ["Waiting for integration..."]
    },
    "function_calls": {
      "status": "pending",
      "logs": ["Waiting for Gemma output..."],
      "calls": []
    }
  }
}
```

## 🔧 Integration Points

### For Teammate (Gemma Integration)

The workflow in `detector/views.py` has placeholders for Gemma integration:

```python
# In process_frame() view:
'gemma': {
    'status': 'pending',  # Update to 'complete' when done
    'enabled': len(paligemma_result['detected_zones']) > 0,
    'logs': ["Your logs here..."],
    'output': None  # Populate with Gemma's response
}
```

**To integrate:**
1. Import your Gemma tool calling module
2. Call it when `enabled=True` (stock-out detected)
3. Update the `gemma` and `function_calls` sections in the response

## 🎨 UI Features

- **Real-time video playback** with looping shelf footage
- **Auto-analysis** every 3 seconds
- **Manual analysis** button for on-demand detection
- **Workflow visualization** with color-coded steps
- **Live logs** for each pipeline stage
- **Gradient dark theme** (purple/blue aesthetic)
- **Responsive design** (works on tablets/desktops)

## 🔒 Privacy & Compliance

- ✅ All processing happens on-device
- ✅ No video data sent to cloud
- ✅ GDPR-compliant architecture
- ✅ Model runs in browser/local backend

## 📊 Performance

- **Model load time**: ~30-40s (first run)
- **Inference time**: ~2-3s per frame
- **Auto-analysis**: Every 3 seconds
- **Memory**: ~5-6GB for model

## 🐛 Troubleshooting

### Video not loading
- Ensure `shelf_demo.mp4` exists in `static/videos/`
- Check browser console for errors
- Try a different video codec (H.264 recommended)

### Model not loading
- Verify `paligemma_stockout_model/` exists
- Check that base model is cached in `~/.cache/huggingface/`
- See console logs: `python3.12 manage.py runserver`

### Slow inference
- First inference is always slower (model loading)
- Subsequent frames should be ~2-3s
- Check if MPS (Metal GPU) is being used

## 🚧 TODO (Teammate Integration)

- [ ] Integrate Gemma LLM for reasoning about stock-outs
- [ ] Implement tool calling for actions (alerts, inventory checks, etc.)
- [ ] Add real backend database for logging detections
- [ ] Deploy to edge device (Raspberry Pi / Jetson Nano)

---

**Built for**: Vusion Shelf Camera Demo
**Tech**: Django + PaliGemma 3B + Gemma + LoRA
**Status**: Demo-ready (awaiting Gemma integration)
