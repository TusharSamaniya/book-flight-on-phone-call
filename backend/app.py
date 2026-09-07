from flask import Flask, request
from twilio.twiml.voice_response import VoiceResponse

app = Flask(__name__)

@app.route("/voice", methods=["POST"])
def voice():
    resp = VoiceResponse()
    resp.say("Hello, I am your AI flight assistant. Where would you like to fly from?", voice="alice")
    resp.record(
        action="/handle-recording",
        method="POST",
        max_length=10,
        play_beep=True
    )
    return str(resp)

import requests
import os
from config import GROQ_API_KEY, GROQ_STT_MODEL

@app.route("/handle-recording", methods=["POST"])
def handle_recording():
    recording_url = request.form.get("RecordingUrl")
    audio_url = recording_url + ".wav"

    audio_response = requests.get(audio_url)
    with open("temp_recording.wav", "wb") as f:
        f.write(audio_response.content)

    transcript = transcribe_audio("temp_recording.wav")
    print("User said:", transcript)

    resp = VoiceResponse()
    resp.say(f"You said: {transcript}. Thank you, goodbye for now.", voice="alice")
    return str(resp)


def transcribe_audio(file_path):
    url = "https://api.groq.com/openai/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
    files = {"file": open(file_path, "rb")}
    data = {"model": GROQ_STT_MODEL}
    response = requests.post(url, headers=headers, files=files, data=data)
    return response.json()["text"]

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)