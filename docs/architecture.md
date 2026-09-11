# Architecture Overview

## Project: AI-Powered Phone Flight Booking Assistant (LiveKit Voice Agent)

This document describes how the components of the LiveKit-powered AI flight booking system operate together.

## Tech Stack

- **Voice Pipeline & Telephony:** LiveKit Cloud / SIP Telephony + LiveKit Agents Framework (`livekit-agents`)
- **Backend Services:** Python (Flask API for Token dispatch + LiveKit Agent Worker)
- **Speech-to-Text (STT):** Groq (Whisper) via `livekit-plugins-groq`
- **Text-to-Speech (TTS):** Groq / Orpheus via `livekit-plugins-groq`
- **Voice Activity Detection (VAD):** Silero VAD via `livekit-plugins-silero`
- **AI Conversation & Tool Calling:** Groq LLM (`llama-3.3-70b-versatile` / `gpt-oss-20b`)
- **Flight Inventory Search:** Duffel API (v2)
- **Payments:** Razorpay (Test mode)
- **Email Confirmation:** Resend API
- **Database:** PostgreSQL (Supabase)
- **Frontend Dashboard:** Next.js (React / Tailwind CSS / Framer Motion)

## System Flow

1. **User calls / connects**: Caller dials the LiveKit SIP phone number or joins via WebRTC room.
2. **LiveKit Agent connects**: The Python agent worker ([backend/agent.py](backend/agent.py)) joins the room as an audio participant.
3. **Full-Duplex Audio & VAD**: Silero VAD detects user speech in real-time, allowing natural interruptions and conversational pacing.
4. **Groq STT**: Transcribes user speech stream into text using Whisper models.
5. **Groq LLM + Function Calling**:
   - Gathers trip preferences (origin, destination, date, passengers, cabin class).
   - Calls `search_available_flights` to query Duffel API for flight offers.
   - Proposes top 3 options (cheapest, fastest, balanced).
   - Invokes `select_flight_option` upon user choice.
   - Collects and validates passenger details (name, phone, email) with `save_passenger_details`.
   - Simulates payment order with `process_payment_and_complete_booking` (Razorpay test mode).
6. **Booking Confirmation**:
   - Generates unique Booking ID (`BK-YYYYMMDD-XXXXXX`).
   - Persists session, passenger, payment, and booking record in Supabase PostgreSQL.
   - Sends HTML booking confirmation email via Resend.
7. **Groq TTS & Voice Response**: Speaks the confirmation ID and details back over the call.
8. **Web Dashboard**: User navigates to the Next.js web application to view their complete itinerary by entering their Booking ID.

## Database Schema (Supabase PostgreSQL)

- **sessions**: `call_sid`, `caller_number`, `current_step`, `responses`, `offers`, `chosen_offer`
- **passengers**: `session_call_sid`, `full_name`, `phone`, `email`, `loyalty_number`
- **payments**: `call_sid`, `order_id`, `payment_id`, `amount`, `currency`, `status`
- **bookings**: `booking_id`, `call_sid`, `flight_offer_id`, `trip_details`, `passenger_name`, `passenger_phone`, `passenger_email`, `price`, `currency`, `status`, `created_at`
