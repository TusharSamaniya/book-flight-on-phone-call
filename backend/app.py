import os
import requests
from flask import Flask, request, send_from_directory
from twilio.twiml.voice_response import VoiceResponse

from config import (
    GROQ_API_KEY,
    GROQ_STT_MODEL,
    GROQ_TTS_MODEL,
    GROQ_TTS_VOICE,
    GROQ_CHAT_MODEL,
)
from conversation import QUESTIONS, get_next_question
from db import create_session, get_session, update_session

app = Flask(__name__)


@app.route("/static_audio/<filename>")
def serve_audio(filename):
    return send_from_directory("static_audio", filename)


@app.route("/voice", methods=["POST"])
def voice():
    call_sid = request.form.get("CallSid")
    caller_number = request.form.get("From")

    create_session(call_sid, caller_number)

    first_question = get_next_question(0)
    synthesize_text(first_question["text"], "question.wav")

    resp = VoiceResponse()
    resp.play(request.url_root + "static_audio/question.wav")
    resp.record(
        action="/handle-recording",
        method="POST",
        max_length=10,
        play_beep=True
    )
    return str(resp)


@app.route("/handle-recording", methods=["POST"])
def handle_recording():
    call_sid = request.form.get("CallSid")
    recording_url = request.form.get("RecordingUrl")
    audio_url = recording_url + ".wav"

    audio_response = requests.get(audio_url)
    with open("temp_recording.wav", "wb") as f:
        f.write(audio_response.content)

    transcript = transcribe_audio("temp_recording.wav")
    print("User said:", transcript)

    session = get_session(call_sid)
    current_step = session["step"]
    responses = session["responses"]
    current_question = QUESTIONS[current_step]

    resp = VoiceResponse()

    # If we couldn't understand the caller, ask them to repeat
    # WITHOUT moving on to the next question.
    if not transcript or transcript.strip() == "":
        synthesize_text(
            "Sorry, I didn't catch that. Could you please repeat?",
            "retry.wav"
        )
        resp.play(request.url_root + "static_audio/retry.wav")
        resp.record(
            action="/handle-recording",
            method="POST",
            max_length=10,
            play_beep=True
        )
        return str(resp)

    # We got a valid answer — save it and move forward.
    responses[current_question["key"]] = transcript
    new_step = current_step + 1
    update_session(call_sid, new_step, responses)

    next_question = get_next_question(new_step)

    if next_question:
        ai_reply = chat_with_ai(transcript, next_question["text"])
        # Fall back to the plain question text if the chat model failed.
        text_to_speak = ai_reply if ai_reply else next_question["text"]

        synthesize_text(text_to_speak, "question.wav")
        resp.play(request.url_root + "static_audio/question.wav")
        resp.record(
            action="/handle-recording",
            method="POST",
            max_length=10,
            play_beep=True
        )
    else:
        synthesize_text("Thank you! I have all the details I need. Goodbye for now.", "reply.wav")
        resp.play(request.url_root + "static_audio/reply.wav")
        print("Final responses:", responses)

    return str(resp)


@app.errorhandler(Exception)
def handle_unexpected_error(error):
    # Catches ANY unhandled crash in our app, so Twilio never just
    # drops the call silently. The caller hears a polite apology
    # instead of dead air or an abrupt hangup.
    print("Unexpected error:", error)
    resp = VoiceResponse()
    resp.say(
        "Sorry, something went wrong on our end. Please try calling again shortly.",
        voice="alice"
    )
    return str(resp)


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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)