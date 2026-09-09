import os
import requests
from flask import Flask, request, send_from_directory, jsonify

from config import (
    GROQ_API_KEY,
    GROQ_STT_MODEL,
    GROQ_TTS_MODEL,
    GROQ_TTS_VOICE,
    GROQ_CHAT_MODEL,
)
from conversation import (
    QUESTIONS,
    get_next_question,
    PASSENGER_QUESTIONS,
    get_next_passenger_question,
)
from db import (
    create_session,
    get_session,
    update_session,
    save_chosen_flight,
    get_offers_from_session,
    save_passenger_info,
    mark_session_ready_for_payment,
)
from flights import search_flights, summarize_flights_for_caller, parse_user_selection
from passenger import validate_passenger_info, get_validation_message, clean_email_transcript
from vonage_auth import generate_vonage_jwt

app = Flask(__name__)


@app.route("/static_audio/<filename>")
def serve_audio(filename):
    return send_from_directory("static_audio", filename)


# ---------------------------------------------------------------------
# Vonage calls this the moment someone dials our number.
# ---------------------------------------------------------------------
@app.route("/answer", methods=["GET", "POST"])
def answer():
    call_sid = request.args.get("conversation_uuid") or request.form.get("conversation_uuid")
    caller_number = request.args.get("from") or request.form.get("from")

    create_session(call_sid, caller_number)

    first_question = get_next_question(0)
    synthesize_text(first_question["text"], "question.wav")

    ncco = [
        {
            "action": "stream",
            "streamUrl": [request.url_root + "static_audio/question.wav"]
        },
        {
            "action": "record",
            "eventUrl": [request.url_root + "recording"],
            "eventMethod": "POST",
            "beepStart": True,
            "endOnSilence": 3,
            "timeOut": 10,
            "format": "wav"
        }
    ]
    return jsonify(ncco)


# ---------------------------------------------------------------------
# Vonage generic call-status webhook — must exist and return 200.
# ---------------------------------------------------------------------
@app.route("/event", methods=["GET", "POST"])
def event():
    return "", 200


# ---------------------------------------------------------------------
# Vonage calls this once a recording is ready.
# We process the audio then push new instructions back to the live call.
# ---------------------------------------------------------------------
@app.route("/recording", methods=["POST"])
def recording():
    data = request.get_json()
    call_sid = data.get("conversation_uuid")
    recording_url = data.get("recording_url")

    # Download and save the audio file
    audio_bytes = download_vonage_recording(recording_url)
    with open("temp_recording.wav", "wb") as f:
        f.write(audio_bytes)

    # Transcribe using Groq Whisper
    transcript = transcribe_audio("temp_recording.wav")
    print("User said:", transcript)

    # Load current session state
    session = get_session(call_sid)
    current_step = session["step"]
    responses = session["responses"]

    # --- Step number reference ---
    # Steps 0-7   → trip detail questions (8 questions)
    # Step 8      → flight search + summarize (auto, no recording)
    # Step 9      → flight selection (SELECTION_STEP)
    # Steps 10-13 → passenger info questions (4 questions)
    # Step 14+    → ready for payment
    SELECTION_STEP = len(QUESTIONS) + 1          # = 9
    PASSENGER_START_STEP = SELECTION_STEP + 1    # = 10

    # ===================================================================
    # MODE 1: PASSENGER INFO COLLECTION (steps 10-13)
    # ===================================================================
    if current_step >= PASSENGER_START_STEP:
        passenger_step = current_step - PASSENGER_START_STEP
        passenger_responses = responses.get("passenger_info", {})
        current_p_question = PASSENGER_QUESTIONS[passenger_step]

        # Handle empty transcript — ask same question again
        if not transcript or transcript.strip() == "":
            synthesize_text(
                "Sorry, I didn't catch that. Could you please repeat?",
                "retry.wav"
            )
            new_ncco = [
                {
                    "action": "stream",
                    "streamUrl": [request.url_root + "static_audio/retry.wav"]
                },
                {
                    "action": "record",
                    "eventUrl": [request.url_root + "recording"],
                    "eventMethod": "POST",
                    "beepStart": True,
                    "endOnSilence": 3,
                    "timeOut": 10,
                    "format": "wav"
                }
            ]
            update_live_call(call_sid, new_ncco)
            return "", 200

        # Clean email transcripts specially
        # (Whisper transcribes "tushar at gmail dot com" literally)
        if current_p_question["key"] == "email":
            transcript = clean_email_transcript(transcript)

        # Save this answer into passenger_info sub-dict
        passenger_responses[current_p_question["key"]] = transcript
        responses["passenger_info"] = passenger_responses

        next_p_question = get_next_passenger_question(passenger_step + 1)

        if next_p_question:
            # Still more passenger questions to ask
            new_step = current_step + 1
            update_session(call_sid, new_step, responses)

            ai_reply = chat_with_ai(transcript, next_p_question["text"])
            text_to_speak = ai_reply if ai_reply else next_p_question["text"]
            synthesize_text(text_to_speak, "p_question.wav")

            new_ncco = [
                {
                    "action": "stream",
                    "streamUrl": [request.url_root + "static_audio/p_question.wav"]
                },
                {
                    "action": "record",
                    "eventUrl": [request.url_root + "recording"],
                    "eventMethod": "POST",
                    "beepStart": True,
                    "endOnSilence": 3,
                    "timeOut": 10,
                    "format": "wav"
                }
            ]

        else:
            # All 4 passenger questions answered — validate them
            errors = validate_passenger_info(passenger_responses)

            if errors:
                # Find the first invalid field and ask for it again
                first_error_field = list(errors.keys())[0]
                retry_msg = get_validation_message(first_error_field)
                synthesize_text(retry_msg, "p_question.wav")

                # Jump back to that specific question's step number
                error_step = PASSENGER_START_STEP + [
                    q["key"] for q in PASSENGER_QUESTIONS
                ].index(first_error_field)
                update_session(call_sid, error_step, responses)

                new_ncco = [
                    {
                        "action": "stream",
                        "streamUrl": [request.url_root + "static_audio/p_question.wav"]
                    },
                    {
                        "action": "record",
                        "eventUrl": [request.url_root + "recording"],
                        "eventMethod": "POST",
                        "beepStart": True,
                        "endOnSilence": 3,
                        "timeOut": 10,
                        "format": "wav"
                    }
                ]

            else:
                # All valid — save to Supabase and mark ready for payment
                save_passenger_info(call_sid, passenger_responses)
                mark_session_ready_for_payment(call_sid)
                update_session(call_sid, current_step + 1, responses)

                confirmation = (
                    f"Thank you, {passenger_responses['full_name']}! "
                    f"I have all your details. "
                    f"We will now process your payment. Please hold on."
                )
                synthesize_text(confirmation, "reply.wav")
                new_ncco = [
                    {
                        "action": "stream",
                        "streamUrl": [request.url_root + "static_audio/reply.wav"]
                    }
                ]

        update_live_call(call_sid, new_ncco)
        return "", 200

    # ===================================================================
    # MODE 2: FLIGHT SELECTION (step 9)
    # ===================================================================
    if current_step == SELECTION_STEP:
        offers = get_offers_from_session(call_sid)
        chosen = parse_user_selection(transcript, offers)

        if chosen:
            save_chosen_flight(call_sid, chosen)
            update_session(call_sid, PASSENGER_START_STEP, responses)

            confirmation = (
                f"Perfect! I've selected the {chosen['airline']} flight "
                f"departing at {chosen['departure_time']} "
                f"for {chosen['price']}. "
            )

            # Immediately ask the first passenger question
            first_p_question = get_next_passenger_question(0)
            synthesize_text(confirmation, "reply.wav")
            synthesize_text(first_p_question["text"], "p_question.wav")

            new_ncco = [
                {
                    "action": "stream",
                    "streamUrl": [request.url_root + "static_audio/reply.wav"]
                },
                {
                    "action": "stream",
                    "streamUrl": [request.url_root + "static_audio/p_question.wav"]
                },
                {
                    "action": "record",
                    "eventUrl": [request.url_root + "recording"],
                    "eventMethod": "POST",
                    "beepStart": True,
                    "endOnSilence": 3,
                    "timeOut": 10,
                    "format": "wav"
                }
            ]

        else:
            # Couldn't understand which option — ask again
            synthesize_text(
                "Sorry, I didn't catch that. "
                "Could you say Option 1, Option 2, or Option 3?",
                "retry.wav"
            )
            new_ncco = [
                {
                    "action": "stream",
                    "streamUrl": [request.url_root + "static_audio/retry.wav"]
                },
                {
                    "action": "record",
                    "eventUrl": [request.url_root + "recording"],
                    "eventMethod": "POST",
                    "beepStart": True,
                    "endOnSilence": 3,
                    "timeOut": 10,
                    "format": "wav"
                }
            ]

        update_live_call(call_sid, new_ncco)
        return "", 200

    # ===================================================================
    # MODE 3: TRIP DETAIL QUESTIONS (steps 0-7)
    # ===================================================================

    # Handle empty transcript — ask same question again
    if not transcript or transcript.strip() == "":
        synthesize_text(
            "Sorry, I didn't catch that. Could you please repeat?",
            "retry.wav"
        )
        new_ncco = [
            {
                "action": "stream",
                "streamUrl": [request.url_root + "static_audio/retry.wav"]
            },
            {
                "action": "record",
                "eventUrl": [request.url_root + "recording"],
                "eventMethod": "POST",
                "beepStart": True,
                "endOnSilence": 3,
                "timeOut": 10,
                "format": "wav"
            }
        ]
        update_live_call(call_sid, new_ncco)
        return "", 200

    # Save this answer and advance step
    current_question = QUESTIONS[current_step]
    responses[current_question["key"]] = transcript
    new_step = current_step + 1
    update_session(call_sid, new_step, responses)

    next_question = get_next_question(new_step)

    if next_question:
        # Still more trip questions to ask
        ai_reply = chat_with_ai(transcript, next_question["text"])
        text_to_speak = ai_reply if ai_reply else next_question["text"]
        synthesize_text(text_to_speak, "question.wav")
        new_ncco = [
            {
                "action": "stream",
                "streamUrl": [request.url_root + "static_audio/question.wav"]
            },
            {
                "action": "record",
                "eventUrl": [request.url_root + "recording"],
                "eventMethod": "POST",
                "beepStart": True,
                "endOnSilence": 3,
                "timeOut": 10,
                "format": "wav"
            }
        ]

    else:
        # All 8 trip questions done — search for flights
        print("All trip responses collected:", responses)
        top_3, error = search_flights(responses)

        if error == "no_flights_found":
            synthesize_text(
                "I'm sorry, I couldn't find any flights for those dates. "
                "Would you like to try a different travel date?",
                "reply.wav"
            )
            update_session(call_sid, 2, responses)
            new_ncco = [
                {
                    "action": "stream",
                    "streamUrl": [request.url_root + "static_audio/reply.wav"]
                },
                {
                    "action": "record",
                    "eventUrl": [request.url_root + "recording"],
                    "eventMethod": "POST",
                    "beepStart": True,
                    "endOnSilence": 3,
                    "timeOut": 10,
                    "format": "wav"
                }
            ]

        elif error:
            synthesize_text(
                "I'm sorry, something went wrong while searching for flights. "
                "Please try calling again shortly.",
                "reply.wav"
            )
            new_ncco = [
                {
                    "action": "stream",
                    "streamUrl": [request.url_root + "static_audio/reply.wav"]
                }
            ]

        else:
            # Success — summarize top 3 and move to selection step
            summary = summarize_flights_for_caller(top_3)
            update_session(call_sid, SELECTION_STEP, responses, top_3)
            synthesize_text(summary, "reply.wav")
            new_ncco = [
                {
                    "action": "stream",
                    "streamUrl": [request.url_root + "static_audio/reply.wav"]
                },
                {
                    "action": "record",
                    "eventUrl": [request.url_root + "recording"],
                    "eventMethod": "POST",
                    "beepStart": True,
                    "endOnSilence": 3,
                    "timeOut": 10,
                    "format": "wav"
                }
            ]

    update_live_call(call_sid, new_ncco)
    return "", 200


# -----------------------------------------------------------------------
# Helper functions
# -----------------------------------------------------------------------

def download_vonage_recording(recording_url):
    token = generate_vonage_jwt()
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(recording_url, headers=headers)
    return response.content


def update_live_call(call_sid, new_ncco):
    """Pushes new NCCO instructions to an ongoing Vonage call."""
    token = generate_vonage_jwt()
    url = f"https://api.nexmo.com/v1/calls/{call_sid}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    body = {
        "action": "transfer",
        "destination": {
            "type": "ncco",
            "ncco": new_ncco
        }
    }
    requests.put(url, headers=headers, json=body)


def transcribe_audio(file_path):
    try:
        url = "https://api.groq.com/openai/v1/audio/transcriptions"
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
        files = {"file": open(file_path, "rb")}
        data = {"model": GROQ_STT_MODEL}
        response = requests.post(url, headers=headers, files=files, data=data)
        return response.json().get("text", "")
    except Exception as e:
        print("STT error:", e)
        return ""


def synthesize_text(text, filename):
    url = "https://api.groq.com/openai/v1/audio/speech"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
    data = {
        "model": GROQ_TTS_MODEL,
        "voice": GROQ_TTS_VOICE,
        "input": text
    }
    response = requests.post(url, headers=headers, json=data)
    filepath = f"static_audio/{filename}"
    with open(filepath, "wb") as f:
        f.write(response.content)
    return filepath


def chat_with_ai(user_input, next_question_text):
    try:
        system_prompt = (
            "You are a friendly AI flight booking assistant speaking on a phone call. "
            "The user just answered your previous question. "
            "Briefly and naturally acknowledge their answer in ONE short sentence, "
            "then smoothly ask this next question: " + next_question_text + " "
            "Keep your entire reply under 25 words. Do not add extra questions."
        )
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
        data = {
            "model": GROQ_CHAT_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input}
            ]
        }
        response = requests.post(url, headers=headers, json=data)
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print("Chat model error:", e)
        return None


@app.errorhandler(Exception)
def handle_unexpected_error(error):
    print("Unexpected error:", error)
    return "", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)