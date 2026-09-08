import requests

from config import DUFFEL_API_KEY, GROQ_API_KEY, GROQ_CHAT_MODEL

# Duffel's current supported API version
DUFFEL_API_VERSION = "v2"
DUFFEL_BASE_URL = "https://api.duffel.com"
DUFFEL_HEADERS = {
    "Authorization": f"Bearer {DUFFEL_API_KEY}",
    "Duffel-Version": DUFFEL_API_VERSION,
    "Content-Type": "application/json",
    "Accept": "application/json"
}


def search_flights(responses):
    """
    Main entry point — takes the raw session responses from the phone
    call, converts them into structured data, searches Duffel, and
    returns the top 3 flight options ready to read aloud.
    """
    search_request = build_search_request(responses)
    offer_request_id = create_offer_request(search_request)
    offers = get_offers(offer_request_id)
    top_3 = select_top_3(offers)
    return top_3


def create_offer_request(search_request):
    """Step 1: Tell Duffel what we're looking for → get an offer_request_id back."""
    url = f"{DUFFEL_BASE_URL}/air/offer_requests"
    body = {"data": search_request}
    response = requests.post(url, headers=DUFFEL_HEADERS, json=body)
    data = response.json()
    return data["data"]["id"]


def get_offers(offer_request_id):
    """Step 2: Use that ID to fetch the actual flight offers."""
    url = f"{DUFFEL_BASE_URL}/air/offers"
    params = {
        "offer_request_id": offer_request_id,
        "sort": "total_amount"
    }
    response = requests.get(url, headers=DUFFEL_HEADERS, params=params)
    data = response.json()
    return data["data"]


def select_top_3(offers):
    """
    Picks the 3 best options from the list of offers:
    - Option 1: cheapest
    - Option 2: fastest
    - Option 3: best balance (middle of sorted list)
    Returns a simplified list of dictionaries easy to read aloud.
    """
    if not offers:
        return []

    # Sort by price to find cheapest
    by_price = sorted(offers, key=lambda o: float(o["total_amount"]))

    # Sort by duration to find fastest
    by_duration = sorted(offers, key=lambda o: get_total_duration(o))

    cheapest = format_offer(by_price[0], "cheapest")

    # Avoid duplicates — only add fastest if it's a different flight
    if len(by_duration) > 1 and by_duration[0]["id"] != by_price[0]["id"]:
        fastest = format_offer(by_duration[0], "fastest")
    else:
        fastest = format_offer(by_price[1], "alternative") if len(by_price) > 1 else None

    # Pick a "balanced" option from the middle of price list
    mid_index = len(by_price) // 2
    balanced_offer = by_price[mid_index]
    if balanced_offer["id"] not in [by_price[0]["id"], by_duration[0]["id"]]:
        balanced = format_offer(balanced_offer, "balanced")
    else:
        balanced = format_offer(by_price[-1], "balanced") if len(by_price) > 2 else None

    return [o for o in [cheapest, fastest, balanced] if o is not None]


def get_total_duration(offer):
    """Adds up all slice durations to get total trip time in minutes."""
    total = 0
    for slice_ in offer.get("slices", []):
        duration_str = slice_.get("duration", "PT0H0M")
        total += parse_iso_duration(duration_str)
    return total


def parse_iso_duration(duration_str):
    """
    Converts ISO 8601 duration like 'PT14H30M' into total minutes.
    PT14H30M = 14 hours 30 minutes = 870 minutes.
    """
    duration_str = duration_str.replace("PT", "")
    hours = 0
    minutes = 0
    if "H" in duration_str:
        parts = duration_str.split("H")
        hours = int(parts[0])
        duration_str = parts[1]
    if "M" in duration_str:
        minutes = int(duration_str.replace("M", ""))
    return hours * 60 + minutes


def format_offer(offer, label):
    """
    Pulls the key info out of a raw Duffel offer dictionary and returns
    a simple, clean dictionary easy to format into a spoken summary.
    """
    slice_ = offer["slices"][0]
    segment = slice_["segments"][0]

    airline = segment["operating_carrier"]["name"]
    departure_time = segment["departing_at"][11:16]   # "HH:MM" from ISO datetime
    arrival_time = segment["arriving_at"][11:16]
    duration_mins = get_total_duration(offer)
    duration_hrs = duration_mins // 60
    duration_remaining_mins = duration_mins % 60
    price = offer["total_amount"]
    currency = offer["total_currency"]
    offer_id = offer["id"]

    return {
        "label": label,
        "offer_id": offer_id,
        "airline": airline,
        "departure_time": departure_time,
        "arrival_time": arrival_time,
        "duration": f"{duration_hrs}h {duration_remaining_mins}m",
        "price": f"{currency} {price}",
    }


def build_search_request(responses):
    """Converts raw call responses into the format Duffel's API expects."""
    origin_code = get_iata_code(responses["origin"])
    destination_code = get_iata_code(responses["destination"])
    passenger_count = extract_passenger_count(responses["passengers"])
    cabin_class = extract_cabin_class(responses["cabin_class"])
    departure_date = extract_date(responses["travel_date"])

    return {
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


def get_iata_code(city_or_airport_name):
    """Converts a spoken city name into its 3-letter IATA airport code."""
    system_prompt = (
        "You convert a spoken city or airport name into its 3-letter "
        "IATA airport code. Reply with ONLY the 3-letter code in "
        "uppercase, nothing else. If there are multiple airports, "
        "use the main/primary international one."
    )
    return ask_groq_simple(system_prompt, city_or_airport_name).strip().upper()


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
    return ask_groq_simple(system_prompt, cabin_text).strip().lower()


def extract_date(date_text):
    """Converts a spoken date like 'next Friday' into YYYY-MM-DD format."""
    system_prompt = (
        "Convert the user's spoken date into strict YYYY-MM-DD format. "
        "Assume the nearest future occurrence of that date. "
        "Reply with ONLY the date in that format, nothing else."
    )
    return ask_groq_simple(system_prompt, date_text).strip()


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