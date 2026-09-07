from flask import Flask, request
from twilio.twiml.voice_response import VoiceResponse
app = Flask(__name__)

@app.route("/voice", methods=["POST"])
def voice():
    resp = VoiceResponse()
    resp.say("Hello, I am your AI flight assistant. Let's book your trip.", voice="alice")
    return str(resp)

import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)