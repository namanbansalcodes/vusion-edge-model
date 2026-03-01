from fastapi import APIRouter
from app.models import VisionEvent
from app.agent import process_event

router = APIRouter(prefix="/api", tags=["events"])


@router.post("/events")
async def receive_vision_event(event: VisionEvent):
    return await process_event(
        camera_id=event.camera_id,
        event_type=event.event_type.value,
        confidence=event.confidence,
        position=event.position.value if event.position else None,
        position_hint=event.position_hint,
        raw_description=event.raw_description,
    )