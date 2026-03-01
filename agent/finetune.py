"""
Fine-tune Gemma on Store #142 tool calling data.

For now: Gemma 3 4B works without fine-tuning via few-shot prompting.
Run this LATER to make it even better using real agent decisions from MySQL.

Usage:
    python finetune.py --from-db --epochs 10
"""

import argparse
import json
import torch
from datasets import Dataset
from transformers import AutoTokenizer, AutoModelForCausalLM, TrainingArguments, Trainer
from peft import LoraConfig, get_peft_model, TaskType

BASE_MODEL = "google/gemma-3-4b-it"
OUTPUT_DIR = "./checkpoints/retail-gemma-4b"

SYSTEM = """You are an autonomous retail store agent. You receive camera events and handle them by calling tools one at a time. Respond with ONLY a tool call or done message.

Tools: lookup_camera, resolve_product, check_stock, find_worker, create_ticket, assign_worker, request_vendor_order, announce

Rules:
- stockout: lookup_camera -> resolve_product -> check_stock -> if backroom>0: create_ticket+find_worker+assign_worker, if backroom=0: create_ticket+request_vendor_order
- fridge_open: lookup_camera -> create_ticket(CRITICAL, 2min) -> find_worker(any) -> assign_worker(URGENT)
- misalignment: lookup_camera -> resolve_product -> create_ticket(LOW, 30min) -> find_worker(stocker) -> assign_worker
- hygiene: lookup_camera -> create_ticket(MEDIUM, 10min) -> find_worker(cleaner) -> assign_worker

Tool call format: <tool_call>{"name": "tool", "arguments": {}}</tool_call>
Done format: <done>summary</done>"""

# Seed examples: (vision_input, [(model_output, tool_result), ...], final_output)
EXAMPLES = [
    # Stockout with backroom stock — full chain
    ("camera_id: CAM-03\nevent_type: stockout\nposition: top-left", [],
     '<tool_call>{"name": "lookup_camera", "arguments": {"camera_id": "CAM-03"}}</tool_call>'),
    ("camera_id: CAM-03\nevent_type: stockout\nposition: top-left",
     [('<tool_call>{"name": "lookup_camera", "arguments": {"camera_id": "CAM-03"}}</tool_call>',
       '{"aisle": 3, "zone": "Pasta/Sauce", "products": [{"sku": "pasta-barilla", "position": "top-left"}, {"sku": "pasta-penne", "position": "top-right"}]}')],
     '<tool_call>{"name": "resolve_product", "arguments": {"camera_id": "CAM-03", "position": "top-left"}}</tool_call>'),
    ("camera_id: CAM-03\nevent_type: stockout\nposition: top-left",
     [('<tool_call>{"name": "lookup_camera", "arguments": {"camera_id": "CAM-03"}}</tool_call>', '{"aisle": 3}'),
      ('<tool_call>{"name": "resolve_product", "arguments": {"camera_id": "CAM-03", "position": "top-left"}}</tool_call>', '{"sku": "pasta-barilla", "name": "Barilla Pasta", "aisle": 3, "row": 2}')],
     '<tool_call>{"name": "check_stock", "arguments": {"product_sku": "pasta-barilla"}}</tool_call>'),
    ("camera_id: CAM-03\nevent_type: stockout\nposition: top-left",
     [('<tool_call>{"name": "check_stock", "arguments": {"product_sku": "pasta-barilla"}}</tool_call>', '{"shelf_qty": 0, "backroom_qty": 24, "vendor_name": "Barilla Direct"}')],
     '<tool_call>{"name": "create_ticket", "arguments": {"ticket_type": "restock", "priority": "HIGH", "source_camera": "CAM-03", "location": "Aisle 3, Row 2", "sla_minutes": 15, "product_sku": "pasta-barilla"}}</tool_call>'),
    ("camera_id: CAM-03\nevent_type: stockout\nposition: top-left",
     [('<tool_call>{"name": "create_ticket", "arguments": {}}</tool_call>', '{"ticket_id": "TKT-0001"}')],
     '<tool_call>{"name": "find_worker", "arguments": {"aisle": 3, "role": "stocker"}}</tool_call>'),
    ("camera_id: CAM-03\nevent_type: stockout\nposition: top-left",
     [('<tool_call>{"name": "create_ticket", "arguments": {}}</tool_call>', '{"ticket_id": "TKT-0001"}'),
      ('<tool_call>{"name": "find_worker", "arguments": {"aisle": 3, "role": "stocker"}}</tool_call>', '{"id": "W2", "name": "Priya", "available": true}')],
     '<tool_call>{"name": "assign_worker", "arguments": {"worker_id": "W2", "ticket_id": "TKT-0001", "announcement": "Priya. Aisle 3 Row 2. Barilla Pasta empty. Backroom has 24 units. Restock within 15 minutes."}}</tool_call>'),
    ("camera_id: CAM-03\nevent_type: stockout\nposition: top-left",
     [('<tool_call>{"name": "assign_worker", "arguments": {}}</tool_call>', '{"assigned": true}')],
     '<done>Stockout CAM-03. Barilla Pasta. Backroom 24 units. TKT-0001 HIGH 15min. Assigned Priya.</done>'),

    # Stockout no backroom — vendor order
    ("camera_id: CAM-04\nevent_type: stockout\nposition: top-left", [],
     '<tool_call>{"name": "lookup_camera", "arguments": {"camera_id": "CAM-04"}}</tool_call>'),
    ("camera_id: CAM-04\nevent_type: stockout\nposition: top-left",
     [('<tool_call>{"name": "lookup_camera", "arguments": {"camera_id": "CAM-04"}}</tool_call>', '{"aisle": 4, "zone": "Snacks", "products": [{"sku": "chips-lays", "position": "top-left"}]}')],
     '<tool_call>{"name": "resolve_product", "arguments": {"camera_id": "CAM-04", "position": "top-left"}}</tool_call>'),
    ("camera_id: CAM-04\nevent_type: stockout\nposition: top-left",
     [('<tool_call>{"name": "resolve_product", "arguments": {}}</tool_call>', '{"sku": "chips-lays", "aisle": 4, "row": 1}')],
     '<tool_call>{"name": "check_stock", "arguments": {"product_sku": "chips-lays"}}</tool_call>'),
    ("camera_id: CAM-04\nevent_type: stockout\nposition: top-left",
     [('<tool_call>{"name": "check_stock", "arguments": {"product_sku": "chips-lays"}}</tool_call>', '{"shelf_qty": 0, "backroom_qty": 0, "reorder_threshold": 15}')],
     '<tool_call>{"name": "create_ticket", "arguments": {"ticket_type": "vendor_order", "priority": "HIGH", "source_camera": "CAM-04", "location": "Aisle 4, Row 1", "sla_minutes": 240, "product_sku": "chips-lays"}}</tool_call>'),
    ("camera_id: CAM-04\nevent_type: stockout\nposition: top-left",
     [('<tool_call>{"name": "create_ticket", "arguments": {}}</tool_call>', '{"ticket_id": "TKT-0002"}')],
     '<tool_call>{"name": "request_vendor_order", "arguments": {"product_sku": "chips-lays", "ticket_id": "TKT-0002", "quantity": 45, "reason": "Shelf and backroom both empty."}}</tool_call>'),
    ("camera_id: CAM-04\nevent_type: stockout\nposition: top-left",
     [('<tool_call>{"name": "request_vendor_order", "arguments": {}}</tool_call>', '{"order_created": true, "auto_approved": false}')],
     '<done>Stockout CAM-04. Lays Classic empty. TKT-0002. Vendor order 45 units. Pending manager.</done>'),

    # Fridge open
    ("camera_id: CAM-01\nevent_type: fridge_open\nconfidence: 0.98", [],
     '<tool_call>{"name": "lookup_camera", "arguments": {"camera_id": "CAM-01"}}</tool_call>'),
    ("camera_id: CAM-01\nevent_type: fridge_open",
     [('<tool_call>{"name": "lookup_camera", "arguments": {"camera_id": "CAM-01"}}</tool_call>', '{"aisle": 1, "zone": "Dairy", "fridge_monitored": true, "fridge_side": "left"}')],
     '<tool_call>{"name": "create_ticket", "arguments": {"ticket_type": "fridge", "priority": "CRITICAL", "source_camera": "CAM-01", "location": "Aisle 1, Dairy fridge, left side", "sla_minutes": 2}}</tool_call>'),
    ("camera_id: CAM-01\nevent_type: fridge_open",
     [('<tool_call>{"name": "create_ticket", "arguments": {}}</tool_call>', '{"ticket_id": "TKT-0003"}')],
     '<tool_call>{"name": "find_worker", "arguments": {"aisle": 1, "role": "any"}}</tool_call>'),
    ("camera_id: CAM-01\nevent_type: fridge_open",
     [('<tool_call>{"name": "create_ticket", "arguments": {}}</tool_call>', '{"ticket_id": "TKT-0003"}'),
      ('<tool_call>{"name": "find_worker", "arguments": {"aisle": 1}}</tool_call>', '{"id": "W1", "name": "Marcus", "available": true}')],
     '<tool_call>{"name": "assign_worker", "arguments": {"worker_id": "W1", "ticket_id": "TKT-0003", "announcement": "URGENT. Marcus. Aisle 1 dairy fridge left side open. Close immediately. 2 minutes."}}</tool_call>'),
    ("camera_id: CAM-01\nevent_type: fridge_open",
     [('<tool_call>{"name": "assign_worker", "arguments": {}}</tool_call>', '{"assigned": true}')],
     '<done>Fridge open CAM-01. CRITICAL 2min. TKT-0003. Assigned Marcus.</done>'),

    # Misalignment
    ("camera_id: CAM-05\nevent_type: misalignment\nposition: middle-left", [],
     '<tool_call>{"name": "lookup_camera", "arguments": {"camera_id": "CAM-05"}}</tool_call>'),
    ("camera_id: CAM-05\nevent_type: misalignment\nposition: middle-left",
     [('<tool_call>{"name": "lookup_camera", "arguments": {"camera_id": "CAM-05"}}</tool_call>', '{"aisle": 5, "zone": "Cereal", "products": [{"sku": "cereal-cheerios", "position": "middle-left"}]}')],
     '<tool_call>{"name": "resolve_product", "arguments": {"camera_id": "CAM-05", "position": "middle-left"}}</tool_call>'),
    ("camera_id: CAM-05\nevent_type: misalignment\nposition: middle-left",
     [('<tool_call>{"name": "resolve_product", "arguments": {}}</tool_call>', '{"sku": "cereal-cheerios", "name": "Cheerios", "aisle": 5, "row": 2}')],
     '<tool_call>{"name": "create_ticket", "arguments": {"ticket_type": "alignment", "priority": "LOW", "source_camera": "CAM-05", "location": "Aisle 5, Row 2", "sla_minutes": 30, "product_sku": "cereal-cheerios"}}</tool_call>'),
    ("camera_id: CAM-05\nevent_type: misalignment",
     [('<tool_call>{"name": "create_ticket", "arguments": {}}</tool_call>', '{"ticket_id": "TKT-0004"}'),
      ('<tool_call>{"name": "find_worker", "arguments": {"aisle": 5, "role": "stocker"}}</tool_call>', '{"id": "W3", "name": "James", "available": true}')],
     '<tool_call>{"name": "assign_worker", "arguments": {"worker_id": "W3", "ticket_id": "TKT-0004", "announcement": "James. Aisle 5 Row 2. Cheerios misaligned. Face and straighten. 30 minutes."}}</tool_call>'),
    ("camera_id: CAM-05\nevent_type: misalignment",
     [('<tool_call>{"name": "assign_worker", "arguments": {}}</tool_call>', '{"assigned": true}')],
     '<done>Misalignment CAM-05. Cheerios Aisle 5. TKT-0004 LOW 30min. Assigned James.</done>'),

    # Hygiene
    ("camera_id: CAM-02\nevent_type: hygiene\nconfidence: 0.91", [],
     '<tool_call>{"name": "lookup_camera", "arguments": {"camera_id": "CAM-02"}}</tool_call>'),
    ("camera_id: CAM-02\nevent_type: hygiene",
     [('<tool_call>{"name": "lookup_camera", "arguments": {"camera_id": "CAM-02"}}</tool_call>', '{"aisle": 2, "zone": "Bakery", "fridge_monitored": false}')],
     '<tool_call>{"name": "create_ticket", "arguments": {"ticket_type": "cleaning", "priority": "MEDIUM", "source_camera": "CAM-02", "location": "Aisle 2, Bakery zone", "sla_minutes": 10}}</tool_call>'),
    ("camera_id: CAM-02\nevent_type: hygiene",
     [('<tool_call>{"name": "create_ticket", "arguments": {}}</tool_call>', '{"ticket_id": "TKT-0005"}'),
      ('<tool_call>{"name": "find_worker", "arguments": {"aisle": 2, "role": "cleaner"}}</tool_call>', '{"id": "W4", "name": "Sofia", "available": true}')],
     '<tool_call>{"name": "assign_worker", "arguments": {"worker_id": "W4", "ticket_id": "TKT-0005", "announcement": "Sofia. Aisle 2, Bakery. Hygiene issue on shelf. Clean and sanitize. 10 minutes."}}</tool_call>'),
    ("camera_id: CAM-02\nevent_type: hygiene",
     [('<tool_call>{"name": "assign_worker", "arguments": {}}</tool_call>', '{"assigned": true}')],
     '<done>Hygiene CAM-02 Aisle 2 Bakery. TKT-0005 MEDIUM 10min. Assigned Sofia.</done>'),

    # Fuzzy position
    ("camera_id: CAM-01\nevent_type: stockout\nposition_hint: upper left near milk",
     [('<tool_call>{"name": "lookup_camera", "arguments": {"camera_id": "CAM-01"}}</tool_call>', '{"aisle": 1, "products": [{"sku": "milk-whole", "position": "top-left"}, {"sku": "milk-2pct", "position": "top-right"}]}')],
     '<tool_call>{"name": "resolve_product", "arguments": {"camera_id": "CAM-01", "position_hint": "upper left near milk"}}</tool_call>'),

    # Auto-approve vendor order
    ("camera_id: CAM-01\nevent_type: stockout\nposition: middle-middle",
     [('<tool_call>{"name": "create_ticket", "arguments": {}}</tool_call>', '{"ticket_id": "TKT-0006"}')],
     '<tool_call>{"name": "request_vendor_order", "arguments": {"product_sku": "butter-unsalted", "ticket_id": "TKT-0006", "quantity": 24, "reason": "Shelf and backroom empty. Perishable dairy."}}</tool_call>'),
    ("camera_id: CAM-01\nevent_type: stockout",
     [('<tool_call>{"name": "request_vendor_order", "arguments": {}}</tool_call>', '{"order_created": true, "auto_approved": true, "cost": 119.76}')],
     '<done>Stockout CAM-01. Butter empty. TKT-0006. Auto-approved 24 units DairyFresh $119.76.</done>'),

    # Second fridge
    ("camera_id: CAM-06\nevent_type: fridge_open", [],
     '<tool_call>{"name": "lookup_camera", "arguments": {"camera_id": "CAM-06"}}</tool_call>'),
    ("camera_id: CAM-06\nevent_type: fridge_open",
     [('<tool_call>{"name": "lookup_camera", "arguments": {"camera_id": "CAM-06"}}</tool_call>', '{"aisle": 1, "zone": "Dairy-Fridge", "fridge_monitored": true, "fridge_side": "right"}')],
     '<tool_call>{"name": "create_ticket", "arguments": {"ticket_type": "fridge", "priority": "CRITICAL", "source_camera": "CAM-06", "location": "Aisle 1, Dairy fridge, right side", "sla_minutes": 2}}</tool_call>'),

    # Bread restock
    ("camera_id: CAM-02\nevent_type: stockout\nposition: middle-left", [],
     '<tool_call>{"name": "lookup_camera", "arguments": {"camera_id": "CAM-02"}}</tool_call>'),
    ("camera_id: CAM-02\nevent_type: stockout\nposition: middle-left",
     [('<tool_call>{"name": "resolve_product", "arguments": {}}</tool_call>', '{"sku": "bread-wonder", "name": "Wonder Bread", "aisle": 2, "row": 3}'),
      ('<tool_call>{"name": "check_stock", "arguments": {"product_sku": "bread-wonder"}}</tool_call>', '{"shelf_qty": 1, "backroom_qty": 12, "reorder_threshold": 8}')],
     '<tool_call>{"name": "create_ticket", "arguments": {"ticket_type": "restock", "priority": "HIGH", "source_camera": "CAM-02", "location": "Aisle 2, Row 3", "sla_minutes": 15, "product_sku": "bread-wonder"}}</tool_call>'),
]


def build_text(vision, history, output):
    parts = ["<start_of_turn>system\n" + SYSTEM + "<end_of_turn>"]
    parts.append("<start_of_turn>user\nVision detection:\n" + vision + "<end_of_turn>")
    for call, result in history:
        parts.append("<start_of_turn>model\n" + call + "<end_of_turn>")
        parts.append("<start_of_turn>user\nResult:\n" + result + "<end_of_turn>")
    parts.append("<start_of_turn>model\n" + output + "<end_of_turn>")
    return "\n".join(parts)


def fetch_db_examples(host, user, password, database):
    import pymysql
    conn = pymysql.connect(host=host, user=user, password=password, db=database, cursorclass=pymysql.cursors.DictCursor)
    texts = []
    with conn.cursor() as cur:
        cur.execute("SELECT DISTINCT event_id FROM agent_log WHERE was_correct IS NULL OR was_correct = TRUE ORDER BY event_id")
        event_ids = [r["event_id"] for r in cur.fetchall()]
        for eid in event_ids:
            cur.execute("SELECT camera_id, event_type, confidence, position, position_hint FROM vision_events WHERE event_id=%s", (eid,))
            ev = cur.fetchone()
            if not ev:
                continue
            cur.execute("SELECT tool_called, tool_arguments, tool_result, model_raw_output FROM agent_log WHERE event_id=%s ORDER BY step_number", (eid,))
            steps = cur.fetchall()
            vi = "camera_id: " + str(ev["camera_id"]) + "\nevent_type: " + str(ev["event_type"])
            if ev.get("position"):
                vi += "\nposition: " + str(ev["position"])
            if ev.get("position_hint"):
                vi += "\nposition_hint: " + str(ev["position_hint"])
            hist = []
            for s in steps:
                if s["model_raw_output"] and s["tool_result"]:
                    texts.append(build_text(vi, list(hist), s["model_raw_output"]))
                    hist.append((s["model_raw_output"], s["tool_result"]))
    conn.close()
    print(f"  Pulled {len(texts)} examples from DB")
    return texts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-db", action="store_true")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--user", default="root")
    parser.add_argument("--password", default="retailagent")
    parser.add_argument("--db", default="store_142")
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--lr", type=float, default=5e-4)
    args = parser.parse_args()

    print("=" * 60)
    print("Fine-tuning", BASE_MODEL, "for Store #142")
    print("=" * 60)

    texts = [build_text(v, h, o) for v, h, o in EXAMPLES]
    print(f"Seed examples: {len(texts)}")

    if args.from_db:
        print("Pulling from database...")
        texts.extend(fetch_db_examples(args.host, args.user, args.password, args.db))

    print(f"Total training examples: {len(texts)}")

    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
        tokenizer.pad_token_id = tokenizer.eos_token_id

    def tokenize(text):
        enc = tokenizer(text, truncation=True, max_length=768, padding="max_length", return_tensors="pt")
        input_ids = enc.input_ids[0]
        attention_mask = enc.attention_mask[0]
        labels = input_ids.clone()
        labels[attention_mask == 0] = -100
        return {"input_ids": input_ids, "attention_mask": attention_mask, "labels": labels}

    tokenized = [tokenize(t) for t in texts]
    dataset = Dataset.from_dict({
        "input_ids": [t["input_ids"] for t in tokenized],
        "attention_mask": [t["attention_mask"] for t in tokenized],
        "labels": [t["labels"] for t in tokenized],
    })
    dataset.set_format("torch")

    print(f"\nLoading {BASE_MODEL}...")
    model = AutoModelForCausalLM.from_pretrained(BASE_MODEL, torch_dtype=torch.float32, device_map="auto")

    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM, r=32, lora_alpha=64,
        lora_dropout=0.1, target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
        bias="none",
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=4,
        learning_rate=args.lr,
        warmup_ratio=0.1,
        logging_steps=2,
        save_strategy="epoch",
        save_total_limit=2,
        fp16=True,
        report_to="none",
        dataloader_drop_last=True,
    )

    trainer = Trainer(model=model, args=training_args, train_dataset=dataset)

    print("\nTraining...")
    trainer.train()

    model.save_pretrained(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)
    print("\n" + "=" * 60)
    print("Saved to", OUTPUT_DIR)
    print("To use: change MODEL_ID in app/agent.py to", OUTPUT_DIR)
    print("=" * 60)


if __name__ == "__main__":
    main()
