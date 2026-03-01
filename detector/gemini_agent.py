"""
Gemini agent for processing stock-out detections with tool calling
Replaces external Gemma service with Google Gemini API
"""
import os
import google.generativeai as genai
from typing import List, Dict, Any


# Configure Gemini (API key from environment)
def configure_gemini():
    """Configure Gemini API with key from environment"""
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set")
    genai.configure(api_key=api_key)


# Tool definitions for retail workflow
RETAIL_TOOLS = [
    {
        "name": "lookup_camera",
        "description": "Get camera details and location information",
        "parameters": {
            "type": "object",
            "properties": {
                "camera_id": {
                    "type": "string",
                    "description": "Camera identifier (e.g., CAM-DEMO-01)"
                }
            },
            "required": ["camera_id"]
        }
    },
    {
        "name": "check_inventory",
        "description": "Check current inventory levels for products in a zone",
        "parameters": {
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
    },
    {
        "name": "create_ticket",
        "description": "Create a maintenance or restocking ticket",
        "parameters": {
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
    },
    {
        "name": "assign_worker",
        "description": "Assign a worker to handle a task",
        "parameters": {
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
    },
    {
        "name": "send_notification",
        "description": "Send notification to store manager or staff",
        "parameters": {
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
    }
]


# Mock tool execution functions
def execute_lookup_camera(camera_id: str) -> Dict:
    """Mock camera lookup"""
    return {
        "camera_id": camera_id,
        "location": "Aisle 3, Section B",
        "status": "active",
        "last_maintenance": "2026-02-20"
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
    "lookup_camera": execute_lookup_camera,
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
            model_name='gemini-2.0-flash',
            tools=RETAIL_TOOLS
        )

        # Build prompt for Gemini
        prompt = f"""You are a retail automation assistant. A vision AI system has detected stock-out issues.

Camera: {camera_id}
Detected Stock-Out Zones: {', '.join(detected_zones)}
Vision AI Analysis: {pali_output}
Shelf Commentary: {commentary}

Your task:
1. Look up camera details
2. Check inventory for affected zones
3. Create restocking tickets for each zone
4. Assign workers to handle the restocking
5. Send notifications if priority is high

Process all {len(detected_zones)} zones and execute the appropriate tools."""

        # Call Gemini
        response = model.generate_content(prompt)

        # Extract tool calls
        tool_calls = []
        tool_results = []

        if hasattr(response, 'candidates') and response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate.content, 'parts'):
                for part in candidate.content.parts:
                    if hasattr(part, 'function_call'):
                        fc = part.function_call
                        tool_name = fc.name
                        tool_args = dict(fc.args)

                        # Execute tool
                        if tool_name in TOOL_EXECUTORS:
                            result = TOOL_EXECUTORS[tool_name](**tool_args)
                            tool_calls.append({
                                'name': tool_name,
                                'arguments': tool_args,
                                'result': result
                            })
                            tool_results.append({
                                'tool': tool_name,
                                'status': 'success',
                                'output': result
                            })

        # Get final response with tool results
        summary = f"Processed {len(detected_zones)} stock-out zones with {len(tool_calls)} tool calls"

        return {
            'status': 'success',
            'zones_processed': len(detected_zones),
            'tool_calls': tool_calls,
            'tool_results': tool_results,
            'summary': summary,
            'raw_response': str(response.text) if hasattr(response, 'text') else 'Tool calls executed'
        }

    except Exception as e:
        return {
            'status': 'error',
            'error': str(e),
            'tool_calls': [],
            'tool_results': []
        }
