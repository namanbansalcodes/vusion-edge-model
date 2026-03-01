from pydantic import BaseModel
from typing import Optional
from enum import Enum


class EventType(str, Enum):
    stockout = "stockout"
    low_stock = "low_stock"
    misalignment = "misalignment"
    fridge_open = "fridge_open"
    fridge_closed = "fridge_closed"
    hygiene = "hygiene"
    unknown = "unknown"


class GridPosition(str, Enum):
    top_left = "top-left"
    top_middle = "top-middle"
    top_right = "top-right"
    middle_left = "middle-left"
    middle_middle = "middle-middle"
    middle_right = "middle-right"
    bottom_left = "bottom-left"
    bottom_middle = "bottom-middle"
    bottom_right = "bottom-right"


class VisionEvent(BaseModel):
    camera_id: str
    event_type: EventType
    confidence: float
    position: Optional[GridPosition] = None
    position_hint: Optional[str] = None
    raw_description: Optional[str] = None


class ManagerDecision(BaseModel):
    ticket_id: str
    approved: bool


class WorkerConfirm(BaseModel):
    ticket_id: str
    worker_id: str
    action: str  # "on_it" | "done"