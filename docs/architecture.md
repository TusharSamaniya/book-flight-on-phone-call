# Architecture Overview

## Project: AI-Powered Phone Flight Booking Assistant

This document describes how the different parts of the system work together.

## Tech Stack

- **Backend:** Python (Flask)
- **Frontend:** Next.js (React)
- **Database:** PostgreSQL (hosted on Supabase)
- **Phone/SMS:** Twilio
- **Flight Search:** Duffel (test mode)
- **Payments:** Razorpay (test mode)
- **Email:** Resend
- **Speech-to-Text (STT):** Groq (Whisper)
- **Text-to-Speech (TTS):** Groq (Orpheus)
- **AI Conversation Logic:** Groq (gpt-oss-20b)

## System Flow

1. **User calls** a Twilio phone number.
2. **Twilio** forwards the call to our **Flask backend** via a webhook.
3. Backend sends the caller's speech to **Groq Whisper (STT)** to convert it into text.
4. Backend sends that text to **Groq's chat model (gpt-oss-20b)** to decide what to ask or say next.
5. Backend sends the AI's reply text to **Groq Orpheus (TTS)** to generate spoken audio.
6. Twilio plays that audio back to the caller.
7. This repeats until all trip details, passenger info, and flight selection are collected.
8. Backend calls **Duffel API** to search and return flight options.
9. Backend calls **Razorpay** (test mode) to simulate payment.
10. Once payment succeeds, backend creates a **booking record** in the **Supabase (PostgreSQL) database**.
11. Backend sends an **SMS via Twilio** with the booking ID and a dashboard link.
12. Backend optionally sends a **confirmation email via Resend**.
13. User can visit the **Next.js web dashboard** to view their booking details.

## Database Schema (Summary)

- **users**: id, name, phone, email
- **bookings**: id, user_id, trip_details, booking_id
- **payments**: id, booking_id, status, amount