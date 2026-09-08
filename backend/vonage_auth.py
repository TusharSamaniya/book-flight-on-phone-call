import time
import uuid
import jwt

from config import VONAGE_APPLICATION_ID, VONAGE_PRIVATE_KEY_PATH


def generate_vonage_jwt():
    """
    Vonage requires every request that controls a call (or downloads a
    recording) to include a short-lived signed token, proving we're
    allowed to act on behalf of our Application. We build that token
    here using our private key file.
    """
    with open(VONAGE_PRIVATE_KEY_PATH, "r") as key_file:
        private_key = key_file.read()

    payload = {
        "application_id": VONAGE_APPLICATION_ID,
        "iat": int(time.time()),
        "exp": int(time.time()) + 60,  # token is valid for 60 seconds
        "jti": str(uuid.uuid4()),      # a unique ID for this specific token
    }

    token = jwt.encode(payload, private_key, algorithm="RS256")
    return token