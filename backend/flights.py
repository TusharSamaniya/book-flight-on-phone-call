import requests
from duffel_api import Duffel

from config import DUFFEL_API_KEY, GROQ_API_KEY, GROQ_CHAT_MODEL

duffel = Duffel(access_token=DUFFEL_API_KEY)


def get_iata_code(city_or_airport_name):
    """
    Converts a spoken city/airport name (e.g. "Delhi") into its
    3-letter IATA airport code (e.g. "DEL") using the Groq chat model.
    """
    system_prompt = (
        "You convert a spoken city or airport name into its 3-letter "
        "IATA airport code. Reply with ONLY the 3-letter code in "
        "uppercase, nothing else. If there are multiple airports, "
        "use the main/primary international one."
    )

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
    data = {
        "model": GROQ_CHAT_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": city_or_airport_name}
        ]
    }
    response = requests.post(url, headers=headers, json=data)
    code = response.json()["choices"][0]["message"]["content"]
    return code.strip().upper()


def build_search_request(responses):
    """
    Takes the raw responses dictionary collected during the phone call
    (Phase 2) and converts it into the structured format Duffel's
    search API expects.
    """
    origin_code = get_iata_code(responses["origin"])
    destination_code = get_iata_code(responses["destination"])

    passenger_count = extract_passenger_count(responses["passengers"])
    cabin_class = extract_cabin_class(responses["cabin_class"])
    departure_date = extract_date(responses["travel_date"])

    search_request = {
        "slices": [
            {
                "origin": origin_code,
                "destination": destination_code,
                "departure_date": departure_date
            }
        ],
        "passengers": [{"type": "adult"} for _ in range(passenger_count)],
        "cabin_class": cabin_class
    }
    return search_request


def extract_passenger_count(passengers_text):
    """Pulls just the number out of something like 'two passengers please'."""
    system_prompt = (
        "Extract ONLY the number of passengers mentioned. "
        "Reply with ONLY a single digit number, nothing else. "
        "If unclear, reply with 1."
    )
    reply = ask_groq_simple(system_prompt, passengers_text)
    try:
        return int(reply.strip())
    except ValueError:
        return 1


def extract_cabin_class(cabin_text):
    """Maps whatever the caller said to Duffel's exact expected values."""
    system_prompt = (
        "Map the user's answer to EXACTLY ONE of these words: "
        "economy, premium_economy, business, first. "
        "Reply with ONLY that one word, nothing else."
    )
    reply = ask_groq_simple(system_prompt, cabin_text)
    return reply.strip().lower()


def extract_date(date_text):
    """Converts a spoken date like 'next Friday' into YYYY-MM-DD format."""
    system_prompt = (
        "Convert the user's spoken date into strict YYYY-MM-DD format. "
        "Assume the nearest future occurrence of that date. "
        "Reply with ONLY the date in that format, nothing else."
    )
    reply = ask_groq_simple(system_prompt, date_text)
    return reply.strip()


def ask_groq_simple(system_prompt, user_text):
    """A small reusable helper for short, single-answer Groq chat calls."""
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
    data = {
        "model": GROQ_CHAT_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text}
        ]
    }
    response = requests.post(url, headers=headers, json=data)
    return response.json()["choices"][0]["message"]["content"]