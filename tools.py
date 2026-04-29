# tools.py
# ─────────────────────────────────────────────────────────────
# All data logic lives here. Swap business? Change appointments.json.
# This file never needs to change between business deployments.
# ─────────────────────────────────────────────────────────────

import json
import os
from datetime import datetime

def load_data(data_file_path: str) -> dict:
    with open(data_file_path, "r") as f:
        return json.load(f)

def save_data(data_file_path: str, data: dict) -> None:
    with open(data_file_path, "w") as f:
        json.dump(data, f, indent=2)

def log_booking(log_path: str, booking: dict) -> None:
    logs = []
    if os.path.exists(log_path):
        with open(log_path, "r") as f:
            logs = json.load(f)
    logs.append(booking)
    with open(log_path, "w") as f:
        json.dump(logs, f, indent=2)

# ── Tool: list_services ──────────────────────────────────────
def list_services(data_file_path: str) -> dict:
    data = load_data(data_file_path)
    services = sorted(set(s["service_type"] for s in data["slots"]))
    dentists = sorted(set(s["dentist_name"] for s in data["slots"]))
    return {
        "services": services,
        "dentists": dentists,
        "message": f"Available services: {', '.join(services)}. "
                   f"Our dentists: {', '.join(dentists)}."
    }

# ── Tool: get_available_slots ────────────────────────────────
def get_available_slots(
    data_file_path: str,
    date: str = None,
    service_type: str = None,
    dentist_name: str = None
) -> dict:
    data = load_data(data_file_path)
    slots = [s for s in data["slots"] if s["status"] == "available"]

    if date:
        # Accept flexible formats: "May 5", "2026-05-05", "05/05"
        parsed_date = _parse_date(date)
        if parsed_date:
            slots = [s for s in slots if s["date"] == parsed_date]
        else:
            return {"available": False, "error": f"Could not parse date: '{date}'. Please use a format like 'May 5' or '2026-05-05'."}

    if service_type:
        slots = [s for s in slots if s["service_type"].lower() == service_type.lower().strip()]

    if dentist_name:
        slots = [s for s in slots if dentist_name.lower() in s["dentist_name"].lower()]

    if not slots:
        return {
            "available": False,
            "count": 0,
            "slots": [],
            "message": "No available slots match those criteria."
        }

    # Return clean summary for Claude to interpret
    return {
        "available": True,
        "count": len(slots),
        "slots": [
            {
                "id": s["id"],
                "dentist": s["dentist_name"],
                "service": s["service_type"],
                "date": s["date"],
                "time": s["time_slot"]
            }
            for s in slots
        ]
    }

# ── Tool: check_slot ─────────────────────────────────────────
def check_slot(
    data_file_path: str,
    slot_id: str
) -> dict:
    data = load_data(data_file_path)
    for s in data["slots"]:
        if s["id"] == slot_id:
            return {
                "found": True,
                "id": s["id"],
                "dentist": s["dentist_name"],
                "service": s["service_type"],
                "date": s["date"],
                "time": s["time_slot"],
                "status": s["status"]
            }
    return {"found": False, "error": f"Slot ID '{slot_id}' not found."}

# ── Tool: confirm_booking ────────────────────────────────────
def confirm_booking(
    data_file_path: str,
    log_path: str,
    slot_id: str,
    patient_name: str,
    patient_contact: str = ""
) -> dict:
    data = load_data(data_file_path)

    for slot in data["slots"]:
        if slot["id"] == slot_id:
            if slot["status"] == "booked":
                return {
                    "success": False,
                    "error": "This slot was just taken. Please choose another."
                }
            # Mark as booked
            slot["status"] = "booked"
            slot["patient_name"] = patient_name
            slot["patient_contact"] = patient_contact
            slot["booked_at"] = datetime.now().isoformat()

            save_data(data_file_path, data)

            booking_record = {
                "slot_id": slot_id,
                "patient_name": patient_name,
                "patient_contact": patient_contact,
                "dentist": slot["dentist_name"],
                "service": slot["service_type"],
                "date": slot["date"],
                "time": slot["time_slot"],
                "booked_at": slot["booked_at"]
            }
            log_booking(log_path, booking_record)

            return {
                "success": True,
                "confirmation": booking_record
            }

    return {"success": False, "error": f"Slot ID '{slot_id}' not found."}

# ── Helpers ──────────────────────────────────────────────────
def _parse_date(raw: str) -> str | None:
    """Try multiple date formats, return YYYY-MM-DD or None."""
    formats = [
        "%Y-%m-%d",       # 2026-05-05
        "%d/%m/%Y",       # 05/05/2026
        "%m/%d/%Y",       # 05/05/2026
        "%B %d",          # May 5  (assumes current year)
        "%B %d, %Y",      # May 5, 2026
        "%b %d",          # May 5
        "%b %d, %Y",      # May 5, 2026
    ]
    raw = raw.strip()
    for fmt in formats:
        try:
            dt = datetime.strptime(raw, fmt)
            # If no year in format, inject current year
            if dt.year == 1900:
                dt = dt.replace(year=datetime.now().year)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None