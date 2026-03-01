"""
Gemini agent for processing stock-out detections with tool calling
Replaces external Gemma service with Google Gemini API
"""
import os
import google.generativeai as genai
from google.generativeai.types import FunctionDeclaration, Tool
from typing import List, Dict, Any


# Configure Gemini (API key from environment)
def configure_gemini():
    """Configure Gemini API with key from environment"""
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set")
    genai.configure(api_key=api_key)


# Define tools using proper Gemini format
send_alert = FunctionDeclaration(
    name="send_alert",
    description="Send an alert to store manager or staff about stock issues",
    parameters={
        "type": "object",
        "properties": {
            "alert_type": {
                "type": "string",
                "enum": ["stocking_needed", "escalate_to_manager", "urgent_restock", "vendor_order_needed"],
                "description": "Type of alert to send"
            },
            "message": {
                "type": "string",
                "description": "Alert message content"
            },
            "zone": {
                "type": "string",
                "description": "Affected shelf zone"
            },
            "severity": {
                "type": "string",
                "enum": ["low", "medium", "high", "critical"],
                "description": "Alert severity level"
            }
        },
        "required": ["alert_type", "message", "zone", "severity"]
    }
)

check_inventory = FunctionDeclaration(
    name="check_inventory",
    description="Check current inventory levels for products in a zone",
    parameters={
        "type": "object",
        "properties": {
            "zone": {
                "type": "string",
                "description": "Shelf zone (e.g., top-left, middle-center)"
            },
            "camera_id": {
                "type": "string",
                "description": "Camera identifier"
            }
        },
        "required": ["zone", "camera_id"]
    }
)

create_ticket = FunctionDeclaration(
    name="create_ticket",
    description="Create a maintenance or restocking ticket",
    parameters={
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Ticket title"
            },
            "description": {
                "type": "string",
                "description": "Detailed description of the issue"
            },
            "priority": {
                "type": "string",
                "enum": ["low", "medium", "high", "urgent"],
                "description": "Ticket priority level"
            },
            "zone": {
                "type": "string",
                "description": "Affected shelf zone"
            }
        },
        "required": ["title", "description", "priority", "zone"]
    }
)

assign_worker = FunctionDeclaration(
    name="assign_worker",
    description="Assign a worker to handle a task",
    parameters={
        "type": "object",
        "properties": {
            "ticket_id": {
                "type": "string",
                "description": "Ticket ID to assign"
            },
            "zone": {
                "type": "string",
                "description": "Work zone location"
            }
        },
        "required": ["ticket_id", "zone"]
    }
)

send_notification = FunctionDeclaration(
    name="send_notification",
    description="Send notification to store manager or staff",
    parameters={
        "type": "object",
        "properties": {
            "recipient": {
                "type": "string",
                "description": "Notification recipient (manager, staff, etc.)"
            },
            "message": {
                "type": "string",
                "description": "Notification message"
            },
            "urgency": {
                "type": "string",
                "enum": ["low", "medium", "high"],
                "description": "Notification urgency"
            }
        },
        "required": ["recipient", "message", "urgency"]
    }
)

# Create tool object
retail_tools = Tool(
    function_declarations=[
        send_alert,
        check_inventory,
        create_ticket,
        assign_worker,
        send_notification
    ]
)


# Mock tool execution functions
def execute_send_alert(alert_type: str, message: str, zone: str, severity: str) -> Dict:
    """Mock alert sending - displays in UI as agent action"""
    import random
    alert_id = f"ALERT-{random.randint(1000, 9999)}"

    # Map alert types to display messages
    alert_messages = {
        "stocking_needed": "🔔 STOCKING UP NEEDED",
        "escalate_to_manager": "⚠️ ESCALATED TO MANAGER",
        "urgent_restock": "🚨 URGENT RESTOCK REQUIRED",
        "vendor_order_needed": "📦 VENDOR ORDER NEEDED"
    }

    return {
        "alert_id": alert_id,
        "type": alert_messages.get(alert_type, alert_type),
        "message": message,
        "zone": zone,
        "severity": severity.upper(),
        "status": "sent",
        "timestamp": "2026-02-28T10:30:00Z"
    }


def execute_check_inventory(zone: str, camera_id: str) -> Dict:
    """Mock inventory check"""
    return {
        "zone": zone,
        "camera_id": camera_id,
        "current_stock": 12,
        "capacity": 48,
        "fill_rate": "25%",
        "status": "low_stock"
    }


def execute_create_ticket(title: str, description: str, priority: str, zone: str) -> Dict:
    """Mock ticket creation"""
    import random
    ticket_id = f"TKT-{random.randint(1000, 9999)}"
    return {
        "ticket_id": ticket_id,
        "title": title,
        "status": "created",
        "priority": priority,
        "zone": zone,
        "created_at": "2026-02-28T10:30:00Z"
    }


def execute_assign_worker(ticket_id: str, zone: str) -> Dict:
    """Mock worker assignment"""
    workers = ["Alice Johnson", "Bob Smith", "Carol Davis"]
    import random
    assigned_worker = random.choice(workers)
    return {
        "ticket_id": ticket_id,
        "worker": assigned_worker,
        "zone": zone,
        "status": "assigned",
        "eta": "15 minutes"
    }


def execute_send_notification(recipient: str, message: str, urgency: str) -> Dict:
    """Mock notification sending"""
    return {
        "recipient": recipient,
        "message": message,
        "urgency": urgency,
        "status": "sent",
        "timestamp": "2026-02-28T10:30:00Z"
    }


# Tool execution router
TOOL_EXECUTORS = {
    "send_alert": execute_send_alert,
    "check_inventory": execute_check_inventory,
    "create_ticket": execute_create_ticket,
    "assign_worker": execute_assign_worker,
    "send_notification": execute_send_notification
}


def process_stockout_with_gemini(
    camera_id: str,
    detected_zones: List[str],
    pali_output: str,
    commentary: str
) -> Dict[str, Any]:
    """
    Process stock-out detection using Gemini with tool calling

    Args:
        camera_id: Camera identifier
        detected_zones: List of zones with stock-outs
        pali_output: Raw PaliGemma output
        commentary: Shelf commentary from PaliGemma

    Returns:
        Dict with tool calls and execution results
    """
    try:
        configure_gemini()

        # Create Gemini model with tools
        model = genai.GenerativeModel(
            model_name='gemini-2.5-flash',
            tools=[retail_tools]
        )

        # Build prompt for Gemini
        prompt = f"""You are an autonomous retail agent. A vision AI has detected stock-out issues that require immediate action.

Camera: {camera_id}
Detected Stock-Out Zones: {', '.join(detected_zones)}
Vision AI Analysis: {pali_output}
Shelf Commentary: {commentary}

Take autonomous action using these tools in order:

1. SEND ALERTS - For each zone, send an appropriate alert:
   - Use send_alert with "stocking_needed" for normal stock-outs
   - Use send_alert with "escalate_to_manager" for critical issues
   - Use send_alert with "urgent_restock" for high-priority zones

2. CHECK INVENTORY - Verify stock levels for affected zones using check_inventory

3. CREATE TICKETS - Generate restocking tickets using create_ticket

4. ASSIGN WORKERS - Dispatch staff to handle restocking using assign_worker

Process all {len(detected_zones)} zones and demonstrate autonomous decision-making."""

        # Call Gemini
        print(f"[Gemini] Calling API for {len(detected_zones)} zones...")
        response = model.generate_content(prompt)

        # Extract tool calls
        tool_calls = []
        response_text = ""

        if hasattr(response, 'candidates') and response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate.content, 'parts'):
                for part in candidate.content.parts:
                    if hasattr(part, 'function_call') and part.function_call:
                        fc = part.function_call
                        tool_name = fc.name
                        tool_args = dict(fc.args)

                        # Mock execute tool (just print and return fake data)
                        print(f"[Mock] Executing {tool_name} with args: {tool_args}")
                        if tool_name in TOOL_EXECUTORS:
                            result = TOOL_EXECUTORS[tool_name](**tool_args)
                            print(f"[Mock] {tool_name} returned: {result}")
                            tool_calls.append({
                                'name': tool_name,
                                'arguments': tool_args,
                                'result': result
                            })
                    elif hasattr(part, 'text'):
                        response_text += part.text

        # Generate summary
        summary = f"Gemini processed {len(detected_zones)} zones and suggested {len(tool_calls)} actions"
        print(f"[Gemini] Complete! {len(tool_calls)} tool calls executed")

        return {
            'status': 'success',
            'zones_processed': len(detected_zones),
            'tool_calls': tool_calls,
            'summary': summary,
            'raw_response': response_text if response_text else f"Executed {len(tool_calls)} tool calls"
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            'status': 'error',
            'error': str(e),
            'tool_calls': [],
            'zones_processed': 0,
            'summary': f'Error: {str(e)}'
        }
