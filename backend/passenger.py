import re
import requests
from config import GROQ_API_KEY, GROQ_CHAT_MODEL


def validate_passenger_info(responses):
    """
    Validates collected passenger info.
    Returns a dict: {"field": "error message"} for any invalid fields.
    Empty dict means everything is valid.
    """
    errors = {}

    # Name: must not be empty
    name = responses.get("full_name", "").strip()
    if not name or len(name) < 2:
        errors["full_name"] = "full name is missing or too short"

    # Phone: must contain at least 10 digits
    phone = responses.get("phone", "")
    digits_only = re.sub(r"\D", "", phone)
    if len(digits_only) < 10:
        errors["phone"] = "phone number must have at least 10 digits"

    # Email: must match standard email format
    email = responses.get("email", "")
    email_pattern = r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
    if not re.match(email_pattern, email.strip()):
        errors["email"] = "email address format is not valid"

    # Loyalty number: optional — skip validation if user said "skip"
    loyalty = responses.get("loyalty_number", "").strip().lower()
    if loyalty in ("skip", "no", "none", "n/a", ""):
        responses["loyalty_number"] = None

    return errors


def get_validation_message(field, ai_rephrase=True):
    """
    Returns a natural, polite retry message for a specific invalid field.
    Uses Groq to rephrase it naturally if ai_rephrase is True.
    """
    base_messages = {
        "full_name": "I didn't catch a valid name. Could you please tell me the full name of the traveler?",
        "phone": "That doesn't seem like a valid phone number. Could you repeat your 10-digit phone number?",
        "email": "That doesn't look like a valid email address. Could you spell it out for me?",
    }

    message = base_messages.get(field, "Could you please repeat that?")

    if not ai_rephrase:
        return message

    try:
        system_prompt = (
            "You are a friendly flight booking assistant on a phone call. "
            "Rephrase this validation message to sound more natural and polite, "
            "in under 20 words: " + message
        )
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
        data = {
            "model": GROQ_CHAT_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message}
            ]
        }
        response = requests.post(url, headers=headers, json=data)
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print("Chat rephrase error:", e)
        return message


def clean_email_transcript(raw_text):
    """
    Whisper often transcribes emails spoken aloud in a messy way.
    e.g. "tushar at gmail dot com" → "tushar@gmail.com"
    This cleans up common spoken patterns.
    """
    text = raw_text.lower().strip()
    text = text.replace(" at ", "@")
    text = text.replace(" dot ", ".")
    text = text.replace(" underscore ", "_")
    text = text.replace(" hyphen ", "-")
    text = text.replace(" ", "")
    return text