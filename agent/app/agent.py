import json
import time
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from app import db
from app.tools import TOOLS, TOOL_DESCRIPTIONS
from app.ws import broadcast

MODEL_ID = "google/gemma-3-4b-it"

_tokenizer = None
_model = None


def load_model():
    global _tokenizer, _model
    if _model is None:
        print(f"Loading {MODEL_ID}...")
        _tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
        _model = AutoModelForCausalLM.from_pretrained(
            MODEL_ID, torch_dtype=torch.bfloat16, device_map="auto"
        )
        print("Model loaded.")
    return _tokenizer, _model


SYSTEM_PROMPT = TOOL_DESCRIPTIONS + """

## RULES — follow exactly, one tool call per turn:

stockout/low_stock:
  1. lookup_camera → 2. resolve_product → 3. check_stock →
  4. create_ticket(restock if backroom>0, vendor_order if backroom=0) →
  5. find_worker+assign_worker (if restock) OR request_vendor_order (if vendor_order) → done

fridge_open:
  1. lookup_camera → 2. create_ticket(CRITICAL, sla=2) → 3. find_worker(any) → 4. assign_worker(URGENT) → done

misalignment:
  1. lookup_camera → 2. resolve_product → 3. create_ticket(LOW, sla=30) → 4. find_worker(stocker) → 5. assign_worker → done

hygiene:
  1. lookup_camera → 2. create_ticket(MEDIUM, sla=10) → 3. find_worker(cleaner) → 4. assign_worker → done

## COMPLETE WORKED EXAMPLE (stockout with backroom stock):

Camera: camera_id: CAM-03, event_type: stockout, position: top-left

Step 1 → <tool_call>{"name": "lookup_camera", "arguments": {"camera_id": "CAM-03"}}</tool_call>
Got: {"aisle": 3, "zone": "Pasta/Sauce", "products": [{"sku": "pasta-barilla", "position": "top-left"}]}

Step 2 → <tool_call>{"name": "resolve_product", "arguments": {"camera_id": "CAM-03", "position": "top-left"}}</tool_call>
Got: {"sku": "pasta-barilla", "name": "Barilla Pasta", "aisle": 3, "row": 2}

Step 3 → <tool_call>{"name": "check_stock", "arguments": {"product_sku": "pasta-barilla"}}</tool_call>
Got: {"shelf_qty": 0, "backroom_qty": 24}

Step 4 → <tool_call>{"name": "create_ticket", "arguments": {"ticket_type": "restock", "priority": "HIGH", "source_camera": "CAM-03", "location": "Aisle 3, Row 2", "sla_minutes": 15, "product_sku": "pasta-barilla"}}</tool_call>
Got: {"ticket_id": "TKT-0001"}

Step 5 → <tool_call>{"name": "find_worker", "arguments": {"aisle": 3, "role": "stocker"}}</tool_call>
Got: {"id": "W2", "name": "Priya", "available": true}

Step 6 → <tool_call>{"name": "assign_worker", "arguments": {"worker_id": "W2", "ticket_id": "TKT-0001", "announcement": "Priya. Aisle 3 Row 2. Barilla Pasta empty. Backroom has 24 units. Restock within 15 minutes."}}</tool_call>
Got: {"assigned": true}

Step 7 → <done>Stockout handled. Barilla Pasta Aisle 3. TKT-0001 assigned to Priya.</done>

## COMPLETE WORKED EXAMPLE (fridge open):

Camera: camera_id: CAM-01, event_type: fridge_open

Step 1 → <tool_call>{"name": "lookup_camera", "arguments": {"camera_id": "CAM-01"}}</tool_call>
Got: {"aisle": 1, "zone": "Dairy", "fridge_monitored": true, "fridge_side": "left"}

Step 2 → <tool_call>{"name": "create_ticket", "arguments": {"ticket_type": "fridge", "priority": "CRITICAL", "source_camera": "CAM-01", "location": "Aisle 1, Dairy fridge, left side", "sla_minutes": 2}}</tool_call>
Got: {"ticket_id": "TKT-0003"}

Step 3 → <tool_call>{"name": "find_worker", "arguments": {"aisle": 1, "role": "any"}}</tool_call>
Got: {"id": "W1", "name": "Marcus", "available": true}

Step 4 → <tool_call>{"name": "assign_worker", "arguments": {"worker_id": "W1", "ticket_id": "TKT-0003", "announcement": "URGENT. Marcus. Aisle 1 dairy fridge left side open. Close immediately. 2 minutes."}}</tool_call>
Got: {"assigned": true}

Step 5 → <done>Fridge open handled. CRITICAL. TKT-0003 assigned to Marcus.</done>

## COMPLETE WORKED EXAMPLE (stockout, no backroom, vendor order):

Camera: camera_id: CAM-04, event_type: stockout, position: top-left

Step 1 → <tool_call>{"name": "lookup_camera", "arguments": {"camera_id": "CAM-04"}}</tool_call>
Got: {"aisle": 4, "zone": "Snacks", "products": [{"sku": "chips-lays", "position": "top-left"}]}

Step 2 → <tool_call>{"name": "resolve_product", "arguments": {"camera_id": "CAM-04", "position": "top-left"}}</tool_call>
Got: {"sku": "chips-lays", "name": "Lays Classic", "aisle": 4, "row": 1}

Step 3 → <tool_call>{"name": "check_stock", "arguments": {"product_sku": "chips-lays"}}</tool_call>
Got: {"shelf_qty": 0, "backroom_qty": 0, "reorder_threshold": 15}

Step 4 → <tool_call>{"name": "create_ticket", "arguments": {"ticket_type": "vendor_order", "priority": "HIGH", "source_camera": "CAM-04", "location": "Aisle 4, Row 1", "sla_minutes": 240, "product_sku": "chips-lays"}}</tool_call>
Got: {"ticket_id": "TKT-0002"}

Step 5 → <tool_call>{"name": "request_vendor_order", "arguments": {"product_sku": "chips-lays", "ticket_id": "TKT-0002", "quantity": 45, "reason": "Shelf and backroom both empty."}}</tool_call>
Got: {"order_created": true, "auto_approved": false}

Step 6 → <done>Stockout handled. Lays Classic empty everywhere. Vendor order placed. Pending manager approval.</done>

## OUTPUT FORMAT — ONLY output one of these, nothing else:

<tool_call>{"name": "tool_name", "arguments": {"param": "value"}}</tool_call>

OR when finished:

<done>brief summary</done>"""


def _build_prompt(vision_input, history):
    parts = ["<start_of_turn>system\n" + SYSTEM_PROMPT + "<end_of_turn>"]
    parts.append("<start_of_turn>user\nCamera detection:\n" + vision_input + "<end_of_turn>")
    for h in history:
        parts.append("<start_of_turn>model\n" + h["call"] + "<end_of_turn>")
        parts.append("<start_of_turn>user\nResult:\n" + json.dumps(h["result"], default=str) + "<end_of_turn>")
    parts.append("<start_of_turn>model\n")
    return "\n".join(parts)


def _generate(prompt):
    tok, mdl = load_model()
    inputs = tok(prompt, return_tensors="pt").to(mdl.device)
    with torch.no_grad():
        out = mdl.generate(
            **inputs, max_new_tokens=200,
            do_sample=False,
            repetition_penalty=1.3,
        )
    return tok.decode(out[0][inputs.input_ids.shape[1]:], skip_special_tokens=True).strip()


def _parse_tool_call(text):
    if "<tool_call>" in text and "</tool_call>" in text:
        raw = text.split("<tool_call>")[1].split("</tool_call>")[0].strip()
        try:
            return json.loads(raw)
        except:
            pass
    if "```json" in text:
        raw = text.split("```json")[1].split("```")[0].strip()
        try:
            return json.loads(raw)
        except:
            pass
    if "```" in text:
        parts = text.split("```")
        if len(parts) >= 3:
            raw = parts[1].strip()
            if raw.startswith("json"):
                raw = raw[4:].strip()
            try:
                return json.loads(raw)
            except:
                pass
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith('{"name"'):
            try:
                return json.loads(line)
            except:
                pass
    return None


def _parse_done(text):
    if "<done>" in text and "</done>" in text:
        return text.split("<done>")[1].split("</done>")[0].strip()
    return None


async def _execute_tool(name, arguments):
    fn = TOOLS.get(name)
    if not fn:
        return {"error": f"Unknown tool: {name}"}
    try:
        return await fn(**arguments)
    except Exception as e:
        return {"error": str(e)}


async def process_event(camera_id, event_type, confidence,
                        position=None, position_hint=None,
                        raw_description=None):
    t0 = time.perf_counter()

    event_id = await db.execute(
        "INSERT INTO vision_events (camera_id, event_type, position, position_hint, raw_description, confidence) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (camera_id, event_type, position, position_hint, raw_description, confidence),
    )

    vision_input = f"camera_id: {camera_id}\nevent_type: {event_type}\nconfidence: {confidence}"
    if position:
        vision_input += f"\nposition: {position}"
    if position_hint:
        vision_input += f"\nposition_hint: {position_hint}"

    history = []
    steps = []

    for step_num in range(1, 11):
        prompt = _build_prompt(vision_input, history)
        response = _generate(prompt)

        print(f"  Step {step_num}: {response[:150]}")

        done_msg = _parse_done(response)
        if done_msg:
            steps.append({"step": step_num, "type": "done", "summary": done_msg})
            await db.execute(
                "INSERT INTO agent_log (event_id, step_number, tool_called, model_raw_output) VALUES (%s,%s,'done',%s)",
                (event_id, step_num, response))
            break

        tool_call = _parse_tool_call(response)
        if not tool_call:
            steps.append({"step": step_num, "type": "parse_error", "raw": response})
            await db.execute(
                "INSERT INTO agent_log (event_id, step_number, tool_called, model_raw_output) VALUES (%s,%s,'parse_error',%s)",
                (event_id, step_num, response))
            break

        result = await _execute_tool(tool_call["name"], tool_call.get("arguments", {}))

        if tool_call["name"] == "resolve_product" and result.get("sku"):
            await db.execute("UPDATE vision_events SET matched_sku=%s WHERE event_id=%s", (result["sku"], event_id))

        ticket_id = result.get("ticket_id")
        if ticket_id:
            await db.execute("UPDATE vision_events SET ticket_id=%s WHERE event_id=%s", (ticket_id, event_id))

        await db.execute(
            "INSERT INTO agent_log (event_id, ticket_id, step_number, tool_called, tool_arguments, tool_result, model_raw_output) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (event_id, ticket_id, step_num, tool_call["name"],
             json.dumps(tool_call.get("arguments", {})),
             json.dumps(result, default=str), response))

        history.append({"call": response, "result": result})
        steps.append({"step": step_num, "tool": tool_call["name"],
                       "args": tool_call.get("arguments", {}), "result": result})

    await db.execute("UPDATE vision_events SET processed=TRUE WHERE event_id=%s", (event_id,))

    trace = {
        "event_id": event_id, "camera_id": camera_id,
        "event_type": event_type, "steps": steps,
        "total_steps": len(steps),
        "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
    }
    await broadcast("agent_trace", trace)
    return trace
