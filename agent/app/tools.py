from app import db
from app.services.tts import speak
from app.ws import broadcast

_ticket_seq = 0


def _next_ticket_id() -> str:
    global _ticket_seq
    _ticket_seq += 1
    return f"TKT-{_ticket_seq:04d}"


async def lookup_camera(camera_id: str) -> dict:
    cam = await db.fetch_one("SELECT * FROM cameras WHERE camera_id = %s", (camera_id,))
    if not cam:
        return {"error": f"Camera {camera_id} not found"}
    products = await db.fetch_all(
        "SELECT cpm.product_sku, cpm.position, i.name, i.category "
        "FROM camera_product_map cpm JOIN inventory i ON cpm.product_sku = i.sku "
        "WHERE cpm.camera_id = %s", (camera_id,))
    return {
        "camera_id": cam["camera_id"], "aisle": cam["aisle"],
        "row_start": cam["row_start"], "row_end": cam["row_end"],
        "zone": cam["zone"], "fridge_monitored": bool(cam["fridge_monitored"]),
        "fridge_side": cam["fridge_side"],
        "products": [{"sku": p["product_sku"], "name": p["name"],
                       "category": p["category"], "position": p["position"]} for p in products],
    }


async def resolve_product(camera_id: str, position: str = None, position_hint: str = None) -> dict:
    if position:
        row = await db.fetch_one(
            "SELECT cpm.product_sku, cpm.position, i.name, i.aisle, i.row_num "
            "FROM camera_product_map cpm JOIN inventory i ON cpm.product_sku = i.sku "
            "WHERE cpm.camera_id = %s AND cpm.position = %s", (camera_id, position))
        if row:
            return {"sku": row["product_sku"], "name": row["name"],
                    "aisle": row["aisle"], "row": row["row_num"],
                    "position": row["position"], "match": "exact"}
    rows = await db.fetch_all(
        "SELECT cpm.product_sku, cpm.position, i.name, i.aisle, i.row_num "
        "FROM camera_product_map cpm JOIN inventory i ON cpm.product_sku = i.sku "
        "WHERE cpm.camera_id = %s", (camera_id,))
    if not rows:
        return {"error": f"No products mapped to camera {camera_id}"}
    if position_hint:
        hint = position_hint.lower()
        for r in rows:
            parts = r["position"].split("-")
            if all(p in hint for p in parts):
                return {"sku": r["product_sku"], "name": r["name"],
                        "aisle": r["aisle"], "row": r["row_num"],
                        "position": r["position"], "match": "fuzzy"}
    return {"match": "ambiguous",
            "products": [{"sku": r["product_sku"], "name": r["name"], "position": r["position"]} for r in rows]}


async def check_stock(product_sku: str) -> dict:
    row = await db.fetch_one(
        "SELECT i.sku, i.name, i.aisle, i.row_num, i.shelf_qty, i.backroom_qty, "
        "i.reorder_threshold, i.max_shelf_capacity, i.unit_cost, i.vendor_id, "
        "v.name AS vendor_name, v.phone AS vendor_phone, v.min_order_qty, v.lead_time_hours "
        "FROM inventory i JOIN vendors v ON i.vendor_id = v.vendor_id WHERE i.sku = %s",
        (product_sku,))
    if not row:
        return {"error": f"SKU {product_sku} not found"}
    return {**row, "unit_cost": float(row["unit_cost"])}


async def find_worker(aisle: int, role: str = "any") -> dict:
    row = await db.fetch_one(
        "SELECT id, name, zone, role, radio_channel FROM workers "
        "WHERE status = 'available' ORDER BY "
        "CASE WHEN zone LIKE %s THEN 0 ELSE 1 END, "
        "CASE WHEN role = %s THEN 0 WHEN role = 'general' THEN 1 "
        "WHEN role = 'supervisor' THEN 2 ELSE 3 END LIMIT 1",
        (f"%{aisle}%", role))
    if not row:
        return {"error": "No workers available", "available": False}
    return {**row, "available": True}


async def create_ticket(ticket_type: str, priority: str, source_camera: str,
                        location: str, sla_minutes: int, product_sku: str = None) -> dict:
    tid = _next_ticket_id()
    await db.execute(
        "INSERT INTO tickets (ticket_id, type, priority, status, source_camera, product_sku, location, sla_minutes) "
        "VALUES (%s, %s, %s, 'open', %s, %s, %s, %s)",
        (tid, ticket_type, priority, source_camera, product_sku, location, sla_minutes))
    await broadcast("ticket_created", {"ticket_id": tid, "type": ticket_type, "priority": priority, "location": location})
    return {"ticket_id": tid, "status": "open"}


async def assign_worker(worker_id: str, ticket_id: str, announcement: str) -> dict:
    await db.execute("UPDATE workers SET status='busy', current_ticket_id=%s WHERE id=%s", (ticket_id, worker_id))
    await db.execute("UPDATE tickets SET assignee_worker_id=%s, status='assigned', assigned_at=NOW() WHERE ticket_id=%s", (worker_id, ticket_id))
    is_urgent = "URGENT" in announcement.upper()
    audio = await speak(announcement, urgent=is_urgent)
    await broadcast("radio_announce", {"worker_id": worker_id, "ticket_id": ticket_id, "message": announcement, "audio": audio, "urgent": is_urgent})
    return {"assigned": True, "worker_id": worker_id, "ticket_id": ticket_id, "audio": audio}


async def request_vendor_order(product_sku: str, ticket_id: str, quantity: int, reason: str) -> dict:
    info = await db.fetch_one(
        "SELECT i.unit_cost, i.vendor_id, i.name AS product_name, "
        "v.name AS vendor_name, v.phone AS vendor_phone, v.min_order_qty, v.lead_time_hours, "
        "m.auto_approve_below, m.name AS manager_name "
        "FROM inventory i JOIN vendors v ON i.vendor_id = v.vendor_id "
        "CROSS JOIN managers m WHERE i.sku = %s LIMIT 1", (product_sku,))
    if not info:
        return {"error": f"SKU {product_sku} not found"}
    order_qty = max(quantity, info["min_order_qty"])
    cost = float(info["unit_cost"]) * order_qty
    auto_approved = cost <= float(info["auto_approve_below"])
    status = "approved" if auto_approved else "pending_approval"
    await db.execute(
        "INSERT INTO vendor_orders (ticket_id, vendor_id, product_sku, quantity, estimated_cost, status) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (ticket_id, info["vendor_id"], product_sku, order_qty, cost, status))
    await db.execute("UPDATE tickets SET status=%s, manager_approved=%s WHERE ticket_id=%s",
                     ("ordered" if auto_approved else "open", auto_approved, ticket_id))
    result = {"order_created": True, "ticket_id": ticket_id, "vendor": info["vendor_name"],
              "vendor_phone": info["vendor_phone"], "product": info["product_name"],
              "quantity": order_qty, "cost": cost, "auto_approved": auto_approved, "status": status}
    if auto_approved:
        msg = f"Auto-approved. Ordering {order_qty} units of {info['product_name']} from {info['vendor_name']} at ${cost:.2f}."
        audio = await speak(msg)
        await broadcast("vendor_order_auto_approved", {**result, "audio": audio})
    else:
        msg = f"Manager {info['manager_name']}, approval needed. {info['product_name']} out of stock. {order_qty} units from {info['vendor_name']} at ${cost:.2f}. Reason: {reason}"
        audio = await speak(msg)
        await broadcast("manager_approval_needed", {**result, "audio": audio, "reason": reason})
    result["audio"] = audio
    return result


async def announce(message: str, urgent: bool = False) -> dict:
    audio = await speak(message, urgent=urgent)
    await broadcast("announcement", {"message": message, "audio": audio, "urgent": urgent})
    return {"announced": True, "audio": audio}


async def check_existing_tickets(camera_id: str, product_sku: str = None) -> dict:
    rows = await db.fetch_all(
        "SELECT ticket_id, type, priority, status, created_at FROM tickets "
        "WHERE status NOT IN ('resolved') AND (source_camera = %s OR product_sku = %s) "
        "ORDER BY created_at DESC LIMIT 5", (camera_id, product_sku))
    return {"count": len(rows), "tickets": rows}


TOOLS = {
    "lookup_camera": lookup_camera,
    "resolve_product": resolve_product,
    "check_stock": check_stock,
    "find_worker": find_worker,
    "create_ticket": create_ticket,
    "assign_worker": assign_worker,
    "request_vendor_order": request_vendor_order,
    "announce": announce,
    "check_existing_tickets": check_existing_tickets,
}

TOOL_DESCRIPTIONS = '''Available tools (each queries the store MySQL database):

1. lookup_camera(camera_id: str) → aisle, zone, fridge info, product list. ALWAYS call first.
2. resolve_product(camera_id: str, position: str?, position_hint: str?) → exact SKU. Exact match then fuzzy.
3. check_stock(product_sku: str) → shelf_qty, backroom_qty, vendor info. Decides restock vs order.
4. find_worker(aisle: int, role: str) → nearest available worker. Roles: stocker, cleaner, supervisor, any.
5. create_ticket(ticket_type, priority, source_camera, location, sla_minutes, product_sku?) → ticket_id.
6. assign_worker(worker_id, ticket_id, announcement) → assigns + speaks announcement via TTS.
7. request_vendor_order(product_sku, ticket_id, quantity, reason) → auto-checks approval threshold.
8. announce(message, urgent) → speaks message over PA.
9. check_existing_tickets(camera_id, product_sku?) → prevents duplicates.'''