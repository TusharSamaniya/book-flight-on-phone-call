"""
Standalone test script — run this locally to verify our Groq integrations
(STT, TTS, Chat) work correctly, WITHOUT needing an actual phone call.

Run with: python test_functions.py
"""

from app import synthesize_text, chat_with_ai

# --- Test 1: Text-to-Speech ---
print("Testing TTS...")
filepath = synthesize_text("Hello, this is a test of the text to speech system.", "test_output.wav")
print(f"TTS saved audio to: {filepath}")
print("-> Open static_audio/test_output.wav and play it to confirm it sounds correct.\n")

# --- Test 2: Chat model ---
print("Testing Chat model...")
ai_reply = chat_with_ai("Delhi", "Where would you like to fly to?")
print(f"AI reply: {ai_reply}")
print("-> Confirm this sounds natural and includes the next question.\n")

# --- Test 3: Speech-to-Text ---
# This requires an actual short audio file to test with.
# Record a few seconds of yourself saying something (e.g. using your
# phone's voice recorder app, or Windows' Voice Recorder), save it as
# "sample_audio.wav" in this same backend folder, then uncomment below.

# from app import transcribe_audio
# print("Testing STT...")
# transcript = transcribe_audio("sample_audio.wav")
# print(f"Transcribed text: {transcript}")