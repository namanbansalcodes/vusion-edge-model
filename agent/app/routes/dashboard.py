from datetime import datetime
from fastapi import APIRouter
from app import db

router = APIRouter(prefix="/api", tags=["dashboard"])


def _serialize(rows):
    for r in rows:
        for k, v in r.items():
            if isinstance(v, datetime): r[k] = v.isoformat()
            elif hasattr(v, "__float__"): r[k] = float(v)
    return rows


@router.get("/tickets")
async def get_tickets(status: str | None = None):
    if status:
        rows = await db.fetch_all("SELECT * FROM tickets WHERE status=%s ORDER BY created_at DESC", (status,))
    else:
        rows = await db.fetch_all("SELECT * FROM tickets ORDER BY created_at DESC")
    return _serialize(rows)


@router.get("/workers")
async def get_workers():
    return await db.fetch_all("SELECT * FROM workers")


@router.get("/inventory")
async def get_inventory():
    rows = await db.fetch_all(
        "SELECT i.*, v.name AS vendor_name, v.phone AS vendor_phone "
        "FROM inventory i JOIN vendors v ON i.vendor_id = v.vendor_id ORDER BY i.shelf_qty ASC")
    return _serialize(rows)


@router.get("/cameras")
async def get_cameras():
    return await db.fetch_all(
        "SELECT c.*, GROUP_CONCAT(CONCAT(cpm.position, ':', cpm.product_sku)) AS product_map "
        "FROM cameras c LEFT JOIN camera_product_map cpm ON c.camera_id = cpm.camera_id GROUP BY c.camera_id")


@router.get("/vendor-orders")
async def get_vendor_orders():
    rows = await db.fetch_all(
        "SELECT vo.*, v.name AS vendor_name, v.phone AS vendor_phone, i.name AS product_name "
        "FROM vendor_orders vo JOIN vendors v ON vo.vendor_id = v.vendor_id "
        "JOIN inventory i ON vo.product_sku = i.sku ORDER BY vo.created_at DESC")
    return _serialize(rows)


@router.get("/agent-log")
async def get_agent_log(limit: int = 50):
    rows = await db.fetch_all(
        "SELECT al.*, ve.camera_id, ve.event_type FROM agent_log al "
        "LEFT JOIN vision_events ve ON al.event_id = ve.event_id "
        "ORDER BY al.created_at DESC LIMIT %s", (limit,))
    return _serialize(rows)


@router.get("/stats")
async def get_stats():
    total = (await db.fetch_one("SELECT COUNT(*) c FROM tickets"))["c"]
    resolved = (await db.fetch_one("SELECT COUNT(*) c FROM tickets WHERE status='resolved'"))["c"]
    events = (await db.fetch_one("SELECT COUNT(*) c FROM vision_events"))["c"]
    cams = (await db.fetch_one("SELECT COUNT(*) c FROM cameras WHERE status='active'"))["c"]
    avg_raw = (await db.fetch_one("SELECT AVG(latency_ms) a FROM agent_log"))["a"]
    return {"total_tickets": total, "resolved": resolved, "open": total - resolved,
            "events_processed": events, "active_cameras": cams,
            "avg_latency_ms": round(float(avg_raw), 2) if avg_raw else 0}