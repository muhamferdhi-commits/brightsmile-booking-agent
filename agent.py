# agent.py
# ─────────────────────────────────────────────────────────────
# BrightSmile Dental Booking Agent
# Powered by Claude via Anthropic Messages API
# Swap config.json + appointments.json to rebrand for any business
# ─────────────────────────────────────────────────────────────

import json
import os
import anthropic
from tools import list_services, get_available_slots, check_slot, confirm_booking

# ── Load config ───────────────────────────────────────────────
def load_config(path: str = "config.json") -> dict:
    with open(path) as f:
        return json.load(f)

# ── Tool definitions (sent to Claude) ─────────────────────────
def get_tool_definitions() -> list:
    return [
        {
            "name": "list_services",
            "description": (
                "Returns all service types and dentist names available at this clinic. "
                "Call this when the patient asks what services are offered or who the dentists are."
            ),
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "get_available_slots",
            "description": (
                "Searches available appointment slots. "
                "Use this to check what's open on a given date, for a service, or with a dentist. "
                "All parameters are optional — combine them to narrow results."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Date to check, e.g. 'May 5', '2026-05-05', '05/05/2026'"
                    },
                    "service_type": {
                        "type": "string",
                        "description": "Service requested, e.g. 'cleaning', 'whitening', 'check-up', 'filling', 'root-canal'"
                    },
                    "dentist_name": {
                        "type": "string",
                        "description": "Partial or full dentist name, e.g. 'Mitchell', 'Dr. Patel'"
                    }
                },
                "required": []
            }
        },
        {
            "name": "check_slot",
            "description": (
                "Fetches full details and current status of a specific slot by its ID. "
                "Use before confirming a booking to verify it's still available."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "slot_id": {
                        "type": "string",
                        "description": "The slot ID, e.g. 'BS012'"
                    }
                },
                "required": ["slot_id"]
            }
        },
        {
            "name": "confirm_booking",
            "description": (
                "Books the appointment and logs it permanently. "
                "Only call this after you have: patient name, slot ID, and explicit patient confirmation. "
                "This action cannot be undone."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "slot_id": {
                        "type": "string",
                        "description": "The slot ID to book"
                    },
                    "patient_name": {
                        "type": "string",
                        "description": "Full name of the patient"
                    },
                    "patient_contact": {
                        "type": "string",
                        "description": "Phone or email of the patient (optional but encouraged)"
                    }
                },
                "required": ["slot_id", "patient_name"]
            }
        }
    ]

# ── Execute tool call ──────────────────────────────────────────
def execute_tool(tool_name: str, tool_input: dict, config: dict) -> str:
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
            data_path,
            log_path,
            slot_id       = tool_input["slot_id"],
            patient_name  = tool_input["patient_name"],
            patient_contact = tool_input.get("patient_contact", "")
        )

    else:
        result = {"error": f"Unknown tool: {tool_name}"}

    return json.dumps(result)

# ── Build system prompt ────────────────────────────────────────
def build_system_prompt(config: dict) -> str:
    return f"""You are {config['agent_name']}, a friendly and professional booking assistant for {config['business_name']}.

Clinic details:
- Address: {config['clinic_address']}
- Phone: {config['contact_number']}
- Hours: {config['clinic_hours']}
- Tagline: {config['tagline']}

Your job is to help patients book appointments. Follow this flow naturally:
1. Greet the patient warmly and ask how you can help.
2. Collect the following — you may gather these in any order as the conversation flows:
   - Patient's full name
   - Preferred service type (use list_services if they're unsure)
   - Preferred date (be flexible: accept "next Monday", "May 5", etc.)
   - Preferred time (morning/afternoon is fine — look up slots that match)
3. Use get_available_slots to find matching openings.
4. Present 2–3 options clearly (dentist, time, date). Don't dump the full list.
5. Once the patient picks a slot, use check_slot to verify it's still open.
6. Ask for confirmation: "Shall I go ahead and book this for you?"
7. Only after explicit "yes" (or clear affirmation) → call confirm_booking.
8. On success, display a formatted confirmation block like this:

╔══════════════════════════════════════════╗
║        ✅  BOOKING CONFIRMED             ║
╠══════════════════════════════════════════╣
║  Patient : [name]                        ║
║  Service : [service]                     ║
║  Dentist : [dentist]                     ║
║  Date    : [date]                        ║
║  Time    : [time]                        ║
║  Clinic  : {config['business_name']}
║  Address : {config['clinic_address']}    ║
║  Phone   : {config['contact_number']}    ║
╚══════════════════════════════════════════╝

Edge cases to handle gracefully:
- No slots available → suggest the nearest available date with openings.
- Invalid or past date → politely ask for a valid future date.
- Patient asks for a booked slot → apologize and offer alternatives immediately.
- Missing info → re-prompt for the specific missing field only, don't restart.
- Patient wants to change something mid-booking → accommodate without losing collected info.

Tone: warm, concise, professional. Max 3 sentences per response unless showing options or confirmations.
Never reveal slot IDs to the patient — use them internally only.
Never make up availability — always check the data file via tools."""

# ── Print confirmation banner ──────────────────────────────────
def print_confirmation(booking: dict, config: dict) -> None:
    width = 46
    print("\n" + "╔" + "═" * width + "╗")
    print("║" + "  ✅  BOOKING CONFIRMED".center(width) + "║")
    print("╠" + "═" * width + "╣")
    for label, value in [
        ("Patient", booking["patient_name"]),
        ("Service", booking["service"].capitalize()),
        ("Dentist", booking["dentist"]),
        ("Date   ", booking["date"]),
        ("Time   ", booking["time"]),
        ("Clinic ", config["business_name"]),
        ("Address", config["clinic_address"]),
        ("Phone  ", config["contact_number"]),
    ]:
        line = f"  {label} : {value}"
        print("║" + line.ljust(width) + "║")
    print("╚" + "═" * width + "╝\n")

# ── Main conversation loop ─────────────────────────────────────
def main():
    config = load_config()
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
    tools  = get_tool_definitions()
    system = build_system_prompt(config)

    print(f"\n{'═' * 50}")
    print(f"  {config['business_name']} — AI Booking Assistant")
    print(f"  Powered by Claude  |  Type 'quit' to exit")
    print(f"{'═' * 50}\n")

    messages: list = []

    # Kick off with a greeting from the agent
    messages.append({"role": "user", "content": "Hello"})

    while True:
        # ── Agentic inner loop: handle tool calls until end_turn ──
        while True:
            response = client.messages.create(
                model      = config["model"],
                max_tokens = config["max_tokens"],
                system     = system,
                tools      = tools,
                messages   = messages
            )

            # Append assistant turn to history
            messages.append({"role": "assistant", "content": response.content})

            # Print any text blocks
            for block in response.content:
                if block.type == "text" and block.text.strip():
                    print(f"\n🦷 {config['agent_name']}: {block.text.strip()}\n")

            if response.stop_reason == "end_turn":
                break

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        print(f"   [Checking data: {block.name}...]")
                        result_str = execute_tool(block.name, block.input, config)
                        tool_results.append({
                            "type"        : "tool_result",
                            "tool_use_id" : block.id,
                            "content"     : result_str
                        })

                        # If booking confirmed, also print the banner
                        if block.name == "confirm_booking":
                            result_data = json.loads(result_str)
                            if result_data.get("success"):
                                print_confirmation(result_data["confirmation"], config)

                messages.append({"role": "user", "content": tool_results})

        # ── Wait for next user input ──────────────────────────────
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nThank you for visiting. Have a great day! 😊")
            break

        if not user_input:
            continue
        if user_input.lower() in {"quit", "exit", "bye", "goodbye"}:
            print(f"\n🦷 {config['agent_name']}: Thank you! See you at your appointment. 😊\n")
            break

        messages.append({"role": "user", "content": user_input})

if __name__ == "__main__":
    main()