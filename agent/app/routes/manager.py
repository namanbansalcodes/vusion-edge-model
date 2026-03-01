from fastapi import APIRouter, HTTPException
from app.models import ManagerDecision
from app import db
from app.services.tts import speak, speak_vendor_call
from app.ws import broadcast

router = APIRouter(prefix="/api/manager", tags=["manager"])


@router.post("/approve")
async def manager_approve(decision: ManagerDecision):
    order = await db.fetch_one(
        "SELECT vo.*, t.product_sku, i.name AS product_name, "
        "v.name AS vendor_name, v.phone AS vendor_phone, v.lead_time_hours "
        "FROM vendor_orders vo JOIN tickets t ON vo.ticket_id = t.ticket_id "
        "JOIN inventory i ON t.product_sku = i.sku "
        "JOIN vendors v ON vo.vendor_id = v.vendor_id WHERE vo.ticket_id = %s",
        (decision.ticket_id,))
    if not order:
        raise HTTPException(404, "Order not found")

    if decision.approved:
        await db.execute("UPDATE vendor_orders SET status='approved', manager_approved_at=NOW() WHERE ticket_id=%s", (decision.ticket_id,))
        await db.execute("UPDATE tickets SET manager_approved=TRUE, status='ordered' WHERE ticket_id=%s", (decision.ticket_id,))

        msg = f"Manager approved. Calling {order['vendor_name']} to order {order['quantity']} units of {order['product_name']}."
        audio = await speak(msg)
        await broadcast("manager_approved", {"ticket_id": decision.ticket_id, "message": msg, "audio": audio})

        await db.execute("UPDATE vendor_orders SET status='calling', call_placed_at=NOW() WHERE ticket_id=%s", (decision.ticket_id,))
        call_segments = await speak_vendor_call(order["vendor_name"], order["product_name"], order["quantity"], order["product_sku"])
        await broadcast("vendor_call_started", {"ticket_id": decision.ticket_id, "vendor": order["vendor_name"], "segments": call_segments})
        await db.execute("UPDATE vendor_orders SET status='confirmed', confirmed_at=NOW() WHERE ticket_id=%s", (decision.ticket_id,))

        return {"status": "approved_and_called", "call_segments": call_segments}
    else:
        await db.execute("UPDATE tickets SET manager_approved=FALSE, status='resolved', resolved_at=NOW() WHERE ticket_id=%s", (decision.ticket_id,))
        await db.execute("UPDATE vendor_orders SET status='denied' WHERE ticket_id=%s", (decision.ticket_id,))
        msg = f"Manager denied order for {order['product_name']}. Ticket closed."
        audio = await speak(msg)
        await broadcast("manager_denied", {"ticket_id": decision.ticket_id, "audio": audio})
        return {"status": "denied"}