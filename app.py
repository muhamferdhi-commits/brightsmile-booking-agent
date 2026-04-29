# app.py — Flask Web Interface for the Booking Agent

from flask import Flask, render_template, request, jsonify, session
import anthropic
import json
import os
import re
import uuid
from tools import list_services, get_available_slots, check_slot, confirm_booking

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'brightsmile-dental-2026-secret')

# Server-side conversation memory
conversations = {}

def load_config():
    with open('config.json') as f:
        return json.load(f)

def get_tool_definitions():
    return [
        {
            "name": "list_services",
            "description": "Returns all service types and dentist names available. Call when patient asks what services are offered.",
            "input_schema": {"type": "object", "properties": {}, "required": []}
        },
        {
            "name": "get_available_slots",
            "description": "Searches available appointment slots by date, service, or dentist.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "Date to check, e.g. 'May 5', '2026-05-05'"},
                    "service_type": {"type": "string", "description": "Service requested, e.g. 'cleaning', 'whitening'"},
                    "dentist_name": {"type": "string", "description": "Partial or full dentist name"}
                },
                "required": []
            }
        },
        {
            "name": "check_slot",
            "description": "Fetches full details and current status of a specific slot by ID.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "slot_id": {"type": "string", "description": "The slot ID, e.g. 'BS012'"}
                },
                "required": ["slot_id"]
            }
        },
        {
            "name": "confirm_booking",
            "description": "Books the appointment. Only call after getting explicit patient confirmation.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "slot_id": {"type": "string"},
                    "patient_name": {"type": "string"},
                    "patient_contact": {"type": "string"}
                },
                "required": ["slot_id", "patient_name"]
            }
        }
    ]

def execute_tool(tool_name, tool_input, config):
    data_path = config["data_file_path"]
    log_path  = config["bookings_log_path"]
    if tool_name == "list_services":
        result = list_services(data_path)
    elif tool_name == "get_available_slots":
        result = get_available_slots(
            data_path,
            date         = tool_input.get("date"),
            service_type = tool_input.get("service_type"),
            dentist_name = tool_input.get("dentist_name")
        )
    elif tool_name == "check_slot":
        result = check_slot(data_path, tool_input["slot_id"])
    elif tool_name == "confirm_booking":
        result = confirm_booking(
            data_path, log_path,
            slot_id         = tool_input["slot_id"],
            patient_name    = tool_input["patient_name"],
            patient_contact = tool_input.get("patient_contact", "")
        )
    else:
        result = {"error": f"Unknown tool: {tool_name}"}
    return json.dumps(result)

def build_system_prompt(config):
    return f"""You are {config['agent_name']}, a friendly and professional booking assistant for {config['business_name']}.

Clinic details:
- Address: {config['clinic_address']}
- Phone: {config['contact_number']}
- Hours: {config['clinic_hours']}

Your job is to help patients book appointments. Follow this flow naturally:
1. Greet the patient warmly on first message.
2. Collect: patient full name, preferred service, preferred date, preferred time.
3. Use get_available_slots to find openings.
4. Present 2-3 options clearly. Never dump the full list.
5. Once patient picks a slot, use check_slot to verify it is still open.
6. Ask: "Shall I go ahead and book this for you?"
7. Only after explicit yes → call confirm_booking.
8. On success, give a warm confirmation message with all details.

Edge cases:
- No slots → suggest nearest available date.
- Invalid date → ask for a valid future date.
- Slot already booked → apologize and offer alternatives.
- Missing info → re-prompt for only the missing field.

Tone: warm, concise, professional. Max 3 sentences unless showing options.
Never reveal slot IDs to patients. Never invent availability — always check via tools.
Do not use markdown symbols like ** or ## in responses. Keep it plain and conversational."""

def run_agent(user_message, session_id, config):
    client = anthropic.Anthropic()

    if session_id not in conversations:
        conversations[session_id] = []

    messages = conversations[session_id]
    messages.append({"role": "user", "content": user_message})

    booking_confirmed = None

    while True:
        response = client.messages.create(
            model      = config["model"],
            max_tokens = config["max_tokens"],
            system     = build_system_prompt(config),
            tools      = get_tool_definitions(),
            messages   = messages
        )
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            break

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result_str = execute_tool(block.name, block.input, config)
                    tool_results.append({
                        "type"        : "tool_result",
                        "tool_use_id" : block.id,
                        "content"     : result_str
                    })
                    if block.name == "confirm_booking":
                        data = json.loads(result_str)
                        if data.get("success"):
                            booking_confirmed = data["confirmation"]
            messages.append({"role": "user", "content": tool_results})

    text = ""
    for block in response.content:
        if hasattr(block, "text"):
            text += block.text

    # Strip leftover markdown formatting
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*',     r'\1', text)

    conversations[session_id] = messages
    return text, booking_confirmed

# ── Routes ────────────────────────────────────────────────────

@app.route('/')
def index():
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    return render_template('index.html', config=load_config())

@app.route('/greet', methods=['POST'])
def greet():
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    session_id = session['session_id']
    config = load_config()
    conversations[session_id] = []
    text, _ = run_agent("Hello", session_id, config)
    return jsonify({"response": text})

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    user_message = data.get('message', '').strip()
    if not user_message:
        return jsonify({"error": "Empty message"}), 400
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    session_id = session['session_id']
    config = load_config()
    text, booking = run_agent(user_message, session_id, config)
    return jsonify({"response": text, "booking": booking})

@app.route('/reset', methods=['POST'])
def reset():
    session_id = session.get('session_id')
    if session_id and session_id in conversations:
        del conversations[session_id]
    session['session_id'] = str(uuid.uuid4())
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)