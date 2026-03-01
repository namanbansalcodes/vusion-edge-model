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
from detector.gemini_agent import process_stockout_with_gemini


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
                    'commentary': paligemma_result['commentary'],
                    'commentary_raw': paligemma_result.get('commentary_raw', ''),
                    'logs': [
                        f"Analyzed frame",
                        f"Stock-outs: {len(paligemma_result['detected_zones'])} zones",
                        f"Zones: {', '.join(paligemma_result['detected_zones']) if paligemma_result['detected_zones'] else 'none'}",
                        f"Observations: {paligemma_result['commentary']}"
                    ]
                },

                # ===== STEP 2: Gemini Agent =====
                'gemini': {},
                'function_calls': {}
            }
        }

        # If stock-out detected, call Gemini for tool calling
        if len(paligemma_result['detected_zones']) > 0:
            try:
                gemini_result = process_stockout_with_gemini(
                    camera_id="CAM-DEMO-01",
                    detected_zones=paligemma_result['detected_zones'],
                    pali_output=paligemma_result['raw_output'],
                    commentary=paligemma_result['commentary']
                )

                if gemini_result['status'] == 'success':
                    # Build logs for Gemini step
                    gemini_logs = [
                        f"Processed {gemini_result['zones_processed']} zones",
                        f"Executed {len(gemini_result['tool_calls'])} tool calls",
                        gemini_result['summary']
                    ]

                    # Format tool calls for display
                    formatted_calls = []
                    for tool_call in gemini_result['tool_calls']:
                        formatted_calls.append({
                            'tool': tool_call['name'],
                            'arguments': tool_call['arguments'],
                            'result': tool_call['result'],
                            'status': 'success'
                        })
                        # Add to logs
                        gemini_logs.append(
                            f"✓ {tool_call['name']}: {list(tool_call['arguments'].values())[0] if tool_call['arguments'] else 'executed'}"
                        )

                    workflow['steps']['gemini'] = {
                        'status': 'complete',
                        'enabled': True,
                        'logs': gemini_logs,
                        'output': gemini_result['summary'],
                        'raw_response': gemini_result.get('raw_response', '')
                    }

                    workflow['steps']['function_calls'] = {
                        'status': 'complete',
                        'logs': [f"Executed {len(formatted_calls)} tool calls successfully"],
                        'calls': formatted_calls
                    }
                else:
                    # Gemini error
                    workflow['steps']['gemini'] = {
                        'status': 'error',
                        'enabled': True,
                        'logs': [f"Gemini error: {gemini_result.get('error', 'Unknown error')}"],
                        'output': None
                    }
                    workflow['steps']['function_calls'] = {
                        'status': 'error',
                        'logs': ["Could not execute due to Gemini error"],
                        'calls': []
                    }

            except Exception as gemini_error:
                workflow['steps']['gemini'] = {
                    'status': 'error',
                    'enabled': True,
                    'logs': [f"Error calling Gemini: {str(gemini_error)}"],
                    'output': None
                }
                workflow['steps']['function_calls'] = {
                    'status': 'error',
                    'logs': ["Could not execute due to error"],
                    'calls': []
                }
        else:
            # No stock-out detected, skip Gemini
            workflow['steps']['gemini'] = {
                'status': 'skipped',
                'enabled': False,
                'logs': ["No stock-out detected - Gemini not called"],
                'output': None
            }
            workflow['steps']['function_calls'] = {
                'status': 'skipped',
                'logs': ["No stock-out to process"],
                'calls': []
            }

        return JsonResponse(workflow)

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["GET"])
def model_status(request):
    """Check if PaliGemma model is loaded and Gemini API is configured"""
    try:
        from detector.inference_utils import is_model_loaded
        import os

        # Check PaliGemma
        pali_loaded = is_model_loaded()

        # Check Gemini API key
        gemini_configured = bool(os.environ.get('GEMINI_API_KEY'))

        return JsonResponse({
            'loaded': pali_loaded,
            'status': 'ready' if pali_loaded else 'loading',
            'paligemma': {
                'loaded': pali_loaded,
                'status': 'ready' if pali_loaded else 'loading'
            },
            'gemini': {
                'configured': gemini_configured,
                'status': 'ready' if gemini_configured else 'not_configured'
            }
        })
    except Exception as e:
        return JsonResponse({
            'loaded': False,
            'status': 'error',
            'error': str(e)
        }, status=500)
