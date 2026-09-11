import os
from flask import Flask, jsonify, request
from livekit import api

from config import (
    LIVEKIT_URL,
    LIVEKIT_API_KEY,
    LIVEKIT_API_SECRET,
)

app = Flask(__name__)


@app.route("/", methods=["GET"])
def health_check():
    return jsonify({
        "status": "online",
        "service": "AI Flight Booking LiveKit Backend",
        "livekit_configured": bool(LIVEKIT_URL and LIVEKIT_API_KEY and LIVEKIT_API_SECRET)
    }), 200


@app.route("/get_token", methods=["GET", "POST"])
def get_livekit_token():
    """
    Generates a LiveKit join token for web clients or SIP trunks to connect
    to the AI Flight Booking room.
    """
    if not (LIVEKIT_API_KEY and LIVEKIT_API_SECRET):
        return jsonify({"error": "LiveKit credentials not configured"}), 500

    room_name = request.args.get("room") or request.json.get("room") if request.is_json else None
    if not room_name:
        room_name = f"flight-booking-room"

    participant_identity = request.args.get("identity") or "user-" + os.urandom(4).hex()

    token = api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET) \
        .with_identity(participant_identity) \
        .with_name("Flight Caller") \
        .with_grants(api.VideoGrants(
            room_join=True,
            room=room_name,
            can_publish=True,
            can_subscribe=True,
        ))

    jwt_token = token.to_jwt()
    return jsonify({
        "server_url": LIVEKIT_URL,
        "room": room_name,
        "identity": participant_identity,
        "token": jwt_token,
    }), 200


@app.errorhandler(Exception)
def handle_unexpected_error(error):
    print("Unexpected error:", error)
    return jsonify({"error": str(error)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
