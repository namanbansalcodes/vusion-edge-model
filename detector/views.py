"""
Views for stock-out detection demo
"""
import json
import base64
import io
from pathlib import Path
from PIL import Image
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

# Import our inference function
import sys
sys.path.append(str(Path(__file__).resolve().parent.parent))
from detector.inference_utils import detect_stockouts


def index(request):
    """Main demo page"""
    # Discover all videos in the media/videos directory
    import os
    from django.conf import settings

    videos_dir = settings.MEDIA_ROOT / 'videos'
    video_files = []

    if videos_dir.exists():
        # Get all video files
        video_extensions = ['.mp4', '.avi', '.mov', '.webm', '.mkv']
        for filename in os.listdir(videos_dir):
            if any(filename.lower().endswith(ext) for ext in video_extensions):
                video_files.append({
                    'name': filename,
                    'url': f"{settings.MEDIA_URL}videos/{filename}"
                })

    # Sort by filename
    video_files.sort(key=lambda x: x['name'])

    return render(request, 'detector/index.html', {
        'videos': video_files,
        'video_count': len(video_files)
    })


@csrf_exempt
@require_http_methods(["POST"])
def process_frame(request):
    """
    Process a single video frame for stock-out detection

    Workflow:
    1. PaliGemma detects stock-out zones
    2. If stock-out found → pass to Gemma (teammate's integration)
    3. Gemma does tool calling

    Expects: POST with base64 encoded image
    Returns: JSON with workflow results
    """
    try:
        data = json.loads(request.body)
        image_data = data.get('image')

        if not image_data:
            return JsonResponse({'error': 'No image provided'}, status=400)

        # Decode base64 image
        if 'base64,' in image_data:
            image_data = image_data.split('base64,')[1]

        image_bytes = base64.b64decode(image_data)
        image = Image.open(io.BytesIO(image_bytes))

        # ===== STEP 1: PaliGemma Detection =====
        paligemma_result = detect_stockouts(image)

        workflow = {
            'success': True,
            'steps': {
                'paligemma': {
                    'status': 'complete',
                    'raw_output': paligemma_result['raw_output'],
                    'detected_zones': paligemma_result['detected_zones'],
                    'zone_count': len(paligemma_result['detected_zones']),
                    'has_stockout': len(paligemma_result['detected_zones']) > 0,
                    'logs': [
                        f"Analyzed frame",
                        f"Detected {len(paligemma_result['detected_zones'])} stock-out zones",
                        f"Zones: {', '.join(paligemma_result['detected_zones']) if paligemma_result['detected_zones'] else 'none'}"
                    ]
                },

                # ===== STEP 2: Gemma (Placeholder for teammate's work) =====
                'gemma': {
                    'status': 'pending',  # Will be 'processing' or 'complete' when integrated
                    'enabled': len(paligemma_result['detected_zones']) > 0,  # Only run if stock-out detected
                    'logs': [
                        "Waiting for integration..." if len(paligemma_result['detected_zones']) > 0
                        else "Skipped (no stock-out detected)"
                    ],
                    'output': None  # Teammate will populate this
                },

                # ===== STEP 3: Function Calls (Placeholder) =====
                'function_calls': {
                    'status': 'pending',
                    'logs': [
                        "Waiting for Gemma output..."
                    ],
                    'calls': []  # Will be populated by tool calling
                }
            }
        }

        return JsonResponse(workflow)

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["GET"])
def model_status(request):
    """Check if PaliGemma model is loaded and ready"""
    try:
        from detector.inference_utils import is_model_loaded
        return JsonResponse({
            'loaded': is_model_loaded(),
            'status': 'ready' if is_model_loaded() else 'loading'
        })
    except Exception as e:
        return JsonResponse({
            'loaded': False,
            'status': 'error',
            'error': str(e)
        }, status=500)
