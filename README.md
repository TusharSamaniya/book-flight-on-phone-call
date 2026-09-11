# ✈️ AI Flight Booking Voice Assistant (LiveKit + Groq)

An AI-powered voice assistant that lets callers book flights over phone calls (LiveKit SIP / WebRTC), searches flight inventory via Duffel, simulates payments via Razorpay, sends email confirmations via Resend, and provides a Next.js itinerary dashboard.

---

## 🛠️ Tech Stack

- **Voice Telephony & WebRTC:** LiveKit Cloud / LiveKit Agents (`livekit-agents`)
- **Speech-to-Text (STT):** Groq Whisper (`whisper-large-v3-turbo`)
- **Language Model & Tool Calling:** Groq LLM (`llama-3.3-70b-versatile`)
- **Text-to-Speech (TTS):** Groq / Orpheus (`canopylabs/orpheus-v1-english`)
- **Voice Activity Detection:** Silero VAD (`livekit-plugins-silero`)
- **Flight Inventory:** Duffel API (v2)
- **Payment Processing:** Razorpay (Test mode)
- **Email Confirmation:** Resend
- **Database:** Supabase (PostgreSQL)
- **Frontend Dashboard:** Next.js (React, Tailwind CSS, Framer Motion)

---

## 🚀 Getting Started

### 1. Environment Variables Setup

Copy `.env.example` to `.env` in the project root and fill in your keys:

```bash
cp .env.example .env
```

Required keys:
- `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `LIVEKIT_PHONE_NUMBER`
- `GROQ_API_KEY`, `GROQ_STT_MODEL`, `GROQ_TTS_MODEL`, `GROQ_TTS_VOICE`, `GROQ_CHAT_MODEL`
- `SUPABASE_URL`, `SUPABASE_KEY`, `DATABASE_URL`
- `DUFFEL_API_KEY`
- `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`
- `RESEND_API_KEY`, `RESEND_FROM_EMAIL`

---

### 2. Backend Setup & Running the Agent

1. Navigate to `backend` and install dependencies:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

2. Run the LiveKit Voice Agent worker:
   ```bash
   python agent.py dev
   ```

3. (Optional) Run the Flask API server for token generation / health checks:
   ```bash
   python app.py
   ```

---

### 3. Frontend Dashboard Setup

1. Navigate to `frontend` and install dependencies:
   ```bash
   cd frontend
   npm install
   ```

2. Start Next.js development server:
   ```bash
   npm run dev
   ```

3. Open [http://localhost:3000](http://localhost:3000) to search and view booking itineraries with your Booking ID (e.g. `BK-20260911-XXXXXX`).
