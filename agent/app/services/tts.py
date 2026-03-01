import os
import uuid
import edge_tts
from app.config import AUDIO_DIR

VOICE_NORMAL = "en-US-GuyNeural"
VOICE_URGENT = "en-US-JennyNeural"

os.makedirs(AUDIO_DIR, exist_ok=True)


async def speak(text: str, urgent: bool = False) -> str:
    voice = VOICE_URGENT if urgent else VOICE_NORMAL
    filename = f"{uuid.uuid4().hex[:12]}.mp3"
    filepath = os.path.join(AUDIO_DIR, filename)
    tts = edge_tts.Communicate(text, voice)
    await tts.save(filepath)
    return f"/static/audio/{filename}"


async def speak_vendor_call(vendor_name: str, product_name: str, quantity: int, sku: str) -> list[dict]:
    ref = uuid.uuid4().hex[:6].upper()
    conversation = [
        ("agent",  f"Hello, this is the automated ordering system from Store 142."),
        ("vendor", f"Hello, {vendor_name} order desk. How can I help you?"),
        ("agent",  f"We need to order {quantity} units of {product_name}, SKU {sku}."),
        ("vendor", f"Let me check. Yes, we have {quantity} units available."),
        ("agent",  f"Can you arrange priority delivery?"),
        ("vendor", f"Priority delivery scheduled for tomorrow morning 6 to 8 AM. Reference number VPO-{ref}."),
        ("agent",  f"Confirmed. Thank you."),
        ("vendor", f"You're welcome. Have a great day."),
    ]
    segments = []
    for speaker, text in conversation:
        audio_url = await speak(text, urgent=(speaker == "vendor"))
        segments.append({"speaker": speaker, "text": text, "audio": audio_url})
    return segments