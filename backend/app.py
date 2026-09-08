import os
import requests
from flask import Flask, request, send_from_directory, jsonify
from flights import search_flights, summarize_flights_for_caller

from config import (
    GROQ_API_KEY,
    GROQ_STT_MODEL,
    GROQ_TTS_MODEL,
    GROQ_TTS_VOICE,
    GROQ_CHAT_MODEL,
)
from conversation import QUESTIONS, get_next_question
from db import create_session, get_session, update_session
from vonage_auth import generate_vonage_jwt

app = Flask(__name__)


@app.route("/static_audio/<filename>")
def serve_audio(filename):
    return send_from_directory("static_audio", filename)


# ---------------------------------------------------------------------
# Vonage calls this the moment someone dials our number. We must reply
# with an NCCO (a JSON list of instructions) telling Vonage what to do.
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
# Vonage's generic call-status webhook (call started, ringing,
# answered, completed, etc). We don't need to act on these events
# right now — we just need this endpoint to exist and respond 200,
# or Vonage will keep retrying and log errors.
# ---------------------------------------------------------------------
@app.route("/event", methods=["GET", "POST"])
def event():
    return "", 200


# ---------------------------------------------------------------------
# Vonage calls this once a recording is ready. Unlike Twilio, this
# does NOT pause the live call waiting for our reply — so once we've
# figured out the next question, we have to actively reach back out
# and update the ongoing call using Vonage's call-control API.
# ---------------------------------------------------------------------
@app.route("/recording", methods=["POST"])
def recording():
    data = request.get_json()
    call_sid = data.get("conversation_uuid")
    recording_url = data.get("recording_url")

    audio_bytes = download_vonage_recording(recording_url)
    with open("temp_recording.wav", "wb") as f:
        f.write(audio_bytes)

    transcript = transcribe_audio("temp_recording.wav")
    print("User said:", transcript)

    session = get_session(call_sid)
    current_step = session["step"]
    responses = session["responses"]
    current_question = QUESTIONS[current_step]

    # If we couldn't understand the caller, ask them to repeat
    # WITHOUT moving on to the next question.
    if not transcript or transcript.strip() == "":
        synthesize_text(
            "Sorry, I didn't catch that. Could you please repeat?",
            "retry.wav"
        )
        new_ncco = [
            {"action": "stream", "streamUrl": [request.url_root + "static_audio/retry.wav"]},
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

    # We got a valid answer — save it and move forward.
    responses[current_question["key"]] = transcript
    new_step = current_step + 1
    update_session(call_sid, new_step, responses)

    next_question = get_next_question(new_step)

    if next_question:
        ai_reply = chat_with_ai(transcript, next_question["text"])
        text_to_speak = ai_reply if ai_reply else next_question["text"]

        synthesize_text(text_to_speak, "question.wav")
        new_ncco = [
            {"action": "stream", "streamUrl": [request.url_root + "static_audio/question.wav"]},
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
        # All questions answered — now search for flights
        print("All responses collected:", responses)
        top_3 = search_flights(responses)

        if top_3:
            summary = summarize_flights_for_caller(top_3)
            # Store offers in session for when user makes their choice
            update_session(call_sid, new_step, responses, top_3)
        else:
            summary = "I'm sorry, I couldn't find any flights for those details. Please try calling again."

        synthesize_text(summary, "reply.wav")
        new_ncco = [
            {"action": "stream", "streamUrl": [request.url_root + "static_audio/reply.wav"]},
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


def download_vonage_recording(recording_url):
    token = generate_vonage_jwt()
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(recording_url, headers=headers)
    return response.content


def update_live_call(call_sid, new_ncco):
    """
    Pushes new instructions to a call that's already in progress —
    this is how we 'continue the conversation' on Vonage, since
    /recording doesn't pause the call the way Twilio's did.
    """
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