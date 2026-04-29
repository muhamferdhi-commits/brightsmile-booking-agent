# AI Appointment Booking Agent
> Powered by Claude (Anthropic) — Built with the Messages API + Tool Use

## Quick Start

```bash
# 1. Clone / download the project
cd brightsmile-booking-agent

# 2. Install dependency (one line)
pip install -r requirements.txt

# 3. Set your Anthropic API key
export ANTHROPIC_API_KEY=sk-ant-...

# 4. Run the agent
python agent.py
```

That's it. The agent will greet you and guide the conversation.

---

## Swapping to a Different Business (Under 60 Seconds)

### Step 1 — Edit `config.json`
```json
{
  "business_name": "GlowUp Salon",          ← change this
  "tagline": "Look good, feel amazing",      ← change this
  "data_file_path": "appointments.json",     ← or point to a new file
  "clinic_address": "18 Oak St, Miami FL",   ← change this
  "contact_number": "+1 305 555 0123",       ← change this
  "clinic_hours": "Tue–Sat, 10 AM – 7 PM",  ← change this
  "agent_name": "Mia"                        ← give the agent a new name
}
```

### Step 2 — Replace `appointments.json`
Keep the exact same field names:
```json
{
  "business": "GlowUp Salon",
  "slots": [
    {
      "id": "GU001",
      "dentist_name": "Stylist Maya",      ← use any staff role label
      "service_type": "haircut",           ← your service names
      "date": "2026-05-05",
      "time_slot": "10:00",
      "status": "available",
      "patient_name": ""
    }
  ]
}
```

**Fields to keep identical:** `id`, `dentist_name`, `service_type`, `date`, `time_slot`, `status`, `patient_name`

### Step 3 — Run again
```bash
python agent.py
```
Done. No code changes required.

---

## File Roles

| File | Role |
|---|---|
| `agent.py` | Conversation loop, tool dispatch, Claude API calls |
| `tools.py` | All data logic — read, search, book, log |
| `appointments.json` | Live data file — this is what Claude reads |
| `config.json` | All branding/config — single place to update |
| `bookings_log.json` | Auto-created — permanent record of all bookings |
| `requirements.txt` | Python dependencies |

---

## Data File Format Reference

```
id            → unique slot identifier (string, e.g. "BS001")
dentist_name  → staff member name (any profession)
service_type  → service offered (any label)
date          → YYYY-MM-DD format
time_slot     → HH:MM (24-hour)
status        → "available" or "booked"
patient_name  → empty string if available
```

## Environment Variable
```bash
ANTHROPIC_API_KEY=sk-ant-your-key-here
```