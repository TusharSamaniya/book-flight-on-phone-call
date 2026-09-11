import asyncio
import logging
from typing import Annotated

from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    Agent,
    AgentSession,
    AutoSubscribe,
    JobContext,
    JobProcess,
    WorkerOptions,
    cli,
    function_tool,
)
from livekit.plugins import groq

from config import (
    GROQ_API_KEY,
    GROQ_CHAT_MODEL,
    GROQ_STT_MODEL,
    GROQ_TTS_MODEL,
    GROQ_TTS_VOICE,
    LIVEKIT_URL,
    LIVEKIT_API_KEY,
    LIVEKIT_API_SECRET,
)
from db import (
    create_session,
    get_session,
    update_session,
    save_chosen_flight,
    save_passenger_info,
    save_payment,
    get_connection,
)
from flights import search_flights
from passenger import validate_passenger_info, clean_email_transcript
from payment import create_payment_order, simulate_payment_success, parse_amount_to_paise
from booking import complete_booking

load_dotenv()
logger = logging.getLogger("flight-booking-agent")
logger.setLevel(logging.INFO)


async def entrypoint(ctx: JobContext):
    logger.info(f"Connecting to LiveKit room: {ctx.room.name}")
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    participant = await ctx.wait_for_participant()
    call_sid = ctx.room.name
    caller_phone = participant.identity or "VoiceCaller"
    logger.info(f"Starting voice booking assistant for participant {caller_phone} in {call_sid}")

    # Initialize DB session
    try:
        create_session(call_sid, caller_phone)
    except Exception as e:
        logger.error(f"Error creating DB session: {e}")

    # Shared state for this call session
    session_state = {
        "trip_data": {},
        "offers": [],
        "chosen_offer": None,
        "passenger_data": {},
    }

    # Define tools using modern livekit-agents @function_tool decorator
    @function_tool()
    async def search_available_flights(
        origin: Annotated[str, "Origin city or airport name, e.g. London, Delhi, or JFK"],
        destination: Annotated[str, "Destination city or airport name, e.g. Paris, Mumbai, or SFO"],
        travel_date: Annotated[str, "Travel date in YYYY-MM-DD or spoken format like 'next Friday' or '2026-10-15'"],
        cabin_class: Annotated[str, "Cabin class: economy, premium_economy, business, or first"] = "economy",
        passengers: Annotated[str, "Number of passengers, default 1"] = "1",
        preferred_time: Annotated[str, "Preferred departure time or 'any'"] = "any",
        budget: Annotated[str, "Budget range or 'any'"] = "any",
        airline_preference: Annotated[str, "Preferred airline or 'any'"] = "any",
    ) -> str:
        """Search for available flights based on trip details collected from the caller."""
        session_state["trip_data"] = {
            "origin": origin,
            "destination": destination,
            "travel_date": travel_date,
            "departure_time": preferred_time,
            "passengers": str(passengers),
            "cabin_class": cabin_class,
            "budget": budget,
            "airline_preference": airline_preference,
        }

        try:
            top_3, error = search_flights(session_state["trip_data"])
            if error:
                return f"Flight search failed: {error}. Please ask the caller to adjust their travel date or details."

            session_state["offers"] = top_3
            update_session(call_sid, 9, session_state["trip_data"], session_state["offers"])

            summary_lines = []
            for i, offer in enumerate(top_3, start=1):
                summary_lines.append(
                    f"Option {i}: {offer['airline']}, departs {offer['departure_time']}, arrives {offer['arrival_time']}, duration {offer['duration']}, price {offer['price']}."
                )

            return (
                "Found flights! Present these options clearly and concisely to the caller and ask which one they prefer:\n"
                + "\n".join(summary_lines)
            )
        except Exception as e:
            logger.error(f"Flight search error: {e}")
            return "An error occurred while querying flight inventory. Please ask the caller to repeat their travel details."

    @function_tool()
    async def select_flight_option(
        option_number: Annotated[int, "The flight option number chosen by caller: 1, 2, or 3"],
    ) -> str:
        """Select one of the presented flight options."""
        offers = session_state.get("offers", [])
        if not offers or option_number < 1 or option_number > len(offers):
            return "Invalid option number. Please ask the caller to choose Option 1, 2, or 3."

        session_state["chosen_offer"] = offers[option_number - 1]
        try:
            save_chosen_flight(call_sid, session_state["chosen_offer"])
            update_session(call_sid, 10, session_state["trip_data"], session_state["offers"])
        except Exception as e:
            logger.error(f"Error saving chosen flight: {e}")

        return (
            f"Flight selected: {session_state['chosen_offer']['airline']} for {session_state['chosen_offer']['price']}. "
            "Now ask the caller for their passenger details: Full Name, 10-digit Phone Number, and Email Address."
        )

    @function_tool()
    async def save_passenger_details(
        full_name: Annotated[str, "Full name of the traveler"],
        phone: Annotated[str, "10-digit phone number"],
        email: Annotated[str, "Email address for ticket delivery"],
        loyalty_number: Annotated[str, "Frequent flyer or loyalty number, or 'skip'"] = "skip",
    ) -> str:
        """Save and validate traveler passenger details."""
        cleaned_email = clean_email_transcript(email)
        data = {
            "full_name": full_name.strip(),
            "phone": phone.strip(),
            "email": cleaned_email,
            "loyalty_number": loyalty_number.strip() if loyalty_number else None,
        }

        errors = validate_passenger_info(data)
        if errors:
            first_err = list(errors.values())[0]
            return f"Validation error: {first_err}. Please politely ask the caller to provide that field again."

        session_state["passenger_data"] = data
        try:
            save_passenger_info(call_sid, data)
            session_state["trip_data"]["passenger_info"] = data
            update_session(call_sid, 14, session_state["trip_data"], session_state["offers"])
        except Exception as e:
            logger.error(f"Error saving passenger data: {e}")

        return "Passenger details successfully saved and validated. Proceed to complete payment."

    @function_tool()
    async def process_payment_and_complete_booking() -> str:
        """Process test payment and finalize the flight booking."""
        chosen_offer = session_state.get("chosen_offer")
        passenger_data = session_state.get("passenger_data")

        if not chosen_offer:
            return "No flight offer has been selected yet."
        if not passenger_data:
            return "Passenger information is incomplete. Please collect passenger details first."

        try:
            order = create_payment_order(chosen_offer)
            if not order:
                return "Payment order creation failed. Please try again."

            payment_result = simulate_payment_success(order["id"])
            currency, amount_paise = parse_amount_to_paise(
                chosen_offer.get("price", "INR 1.00")
            )

            payment_result["amount"] = amount_paise
            payment_result["currency"] = currency

            save_payment(
                call_sid=call_sid,
                order_id=order["id"],
                payment_id=payment_result["payment_id"],
                amount=amount_paise,
                currency=currency,
                status=payment_result["status"],
            )

            dashboard_url = "https://your-vercel-app.vercel.app/booking"
            booking_res = complete_booking(
                db_conn_func=get_connection,
                call_sid=call_sid,
                chosen_offer=chosen_offer,
                trip_responses=session_state["trip_data"],
                passenger_responses=passenger_data,
                payment_result=payment_result,
                dashboard_url=dashboard_url,
            )

            return (
                f"Booking completed successfully! Booking ID is {booking_res['booking_id']}. "
                f"Confirmation email sent to {passenger_data['email']}. "
                f"Read out the booking ID clearly to the caller, confirm email was sent, and thank them."
            )

        except Exception as e:
            logger.error(f"Booking completion error: {e}")
            return "Payment processing failed. Please ask the caller if they would like to retry."

    system_instructions = (
        "You are a friendly, professional AI flight booking assistant on a phone call. "
        "Guide the caller through booking their flight step by step:\n"
        "1. Collect trip details: Origin, Destination, Travel date, Preferred departure time, Passenger count, Cabin class, and Budget.\n"
        "2. Once you have origin, destination, and travel date, call `search_available_flights`.\n"
        "3. Read the top 3 options clearly and ask which option the caller wants.\n"
        "4. Call `select_flight_option` with their choice.\n"
        "5. Ask for their Full Name, Phone Number, and Email, then call `save_passenger_details`.\n"
        "6. Call `process_payment_and_complete_booking` to finalize the reservation and trigger the confirmation email.\n"
        "7. Spell out the Booking ID clearly to the caller.\n\n"
        "Voice conversation rules:\n"
        "- Keep responses conversational, concise, and under 25 words per turn.\n"
        "- Ask only ONE question at a time.\n"
        "- Be polite, warm, and natural."
    )

    agent = Agent(
        instructions=system_instructions,
        tools=[
            search_available_flights,
            select_flight_option,
            save_passenger_details,
            process_payment_and_complete_booking,
        ],
    )

    session = AgentSession(
        stt=groq.STT(
            model=GROQ_STT_MODEL or "whisper-large-v3-turbo",
            api_key=GROQ_API_KEY,
        ),
        llm=groq.LLM(
            model=GROQ_CHAT_MODEL or "llama-3.3-70b-versatile",
            api_key=GROQ_API_KEY,
        ),
        tts=groq.TTS(
            model=GROQ_TTS_MODEL or "canopylabs/orpheus-v1-english",
            voice=GROQ_TTS_VOICE or "autumn",
            api_key=GROQ_API_KEY,
        ),
    )

    await session.start(agent, room=ctx.room)
    await session.say("Hi there! I am your AI flight booking assistant. Where would you like to fly from?")


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
        )
    )
