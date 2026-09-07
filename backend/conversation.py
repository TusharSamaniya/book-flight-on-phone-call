QUESTIONS = [
    {"key": "origin", "text": "Where would you like to fly from?"},
    {"key": "destination", "text": "Where would you like to fly to?"},
    {"key": "travel_date", "text": "What date would you like to travel?"},
    {"key": "departure_time", "text": "Do you have a preferred departure time?"},
    {"key": "passengers", "text": "How many passengers will be flying?"},
    {"key": "cabin_class", "text": "Which cabin class would you like — economy, premium, business, or first?"},
    {"key": "budget", "text": "What is your budget range for this trip?"},
    {"key": "airline_preference", "text": "Do you have any airline preference, or should I search all airlines?"},
]

def get_next_question(current_step):
    if current_step >= len(QUESTIONS):
        return None
    return QUESTIONS[current_step]