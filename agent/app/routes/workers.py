from fastapi import APIRouter, HTTPException
from app.models import WorkerConfirm
from app import db
from app.services.tts import speak
from app.ws import broadcast

router = APIRouter(prefix="/api/worker", tags=["workers"])


@router.post("/confirm")
async def worker_confirm(conf: WorkerConfirm):
    ticket = await db.fetch_one("SELECT * FROM tickets WHERE ticket_id = %s", (conf.ticket_id,))
    if not ticket:
        raise HTTPException(404, "Ticket not found")

    worker = await db.fetch_one("SELECT name FROM workers WHERE id=%s", (conf.worker_id,))
    name = worker["name"] if worker else "Worker"

    if conf.action == "on_it":
        await db.execute("UPDATE tickets SET status='in_progress' WHERE ticket_id=%s", (conf.ticket_id,))
        msg = f"Copy that {name}. Ticket {conf.ticket_id} in progress."
    elif conf.action == "done":
        await db.execute("UPDATE tickets SET status='resolved', resolved_at=NOW() WHERE ticket_id=%s", (conf.ticket_id,))
        await db.execute("UPDATE workers SET status='available', current_ticket_id=NULL WHERE id=%s", (conf.worker_id,))
        msg = f"Confirmed. Ticket {conf.ticket_id} resolved. Thank you {name}."
    else:
        raise HTTPException(400, "action must be 'on_it' or 'done'")

    audio = await speak(msg)
    await broadcast("worker_update", {"ticket_id": conf.ticket_id, "worker_id": conf.worker_id, "action": conf.action, "message": msg, "audio": audio})
    return {"status": conf.action, "message": msg, "audio": audio}