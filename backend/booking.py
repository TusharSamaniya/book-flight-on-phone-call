import uuid
import json
from datetime import datetime

import resend

from config import (
    RESEND_API_KEY,
    RESEND_FROM_EMAIL,
)


# -----------------------------------------------------------------------
# Unique booking ID generator
# e.g. "BK-20260909-XYZ123"
# -----------------------------------------------------------------------
def generate_booking_id():
    date_part = datetime.now().strftime("%Y%m%d")
    random_part = str(uuid.uuid4()).upper()[:6]
    return f"BK-{date_part}-{random_part}"


# -----------------------------------------------------------------------
# Save booking record to Supabase
# -----------------------------------------------------------------------
def save_booking_record(db_conn_func, call_sid, booking_id, chosen_offer,
                        trip_responses, passenger_responses,
                        payment_result):
    """
    Inserts a complete booking record into our bookings table.
    db_conn_func is the get_connection function from db.py.
    """
    import psycopg2.extras

    conn = db_conn_func()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO bookings (
            booking_id, call_sid, flight_offer_id,
            trip_details, passenger_name, passenger_phone,
            passenger_email, price, currency, status
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            booking_id,
            call_sid,
            chosen_offer.get("offer_id", ""),
            json.dumps(trip_responses),
            passenger_responses.get("full_name", ""),
            passenger_responses.get("phone", ""),
            passenger_responses.get("email", ""),
            payment_result.get("amount", 0),
            payment_result.get("currency", "INR"),
            "confirmed"
        )
    )
    conn.commit()
    cur.close()
    conn.close()


# -----------------------------------------------------------------------
# Email via Resend
# -----------------------------------------------------------------------
def send_email_confirmation(to_email, booking_id, chosen_offer,
                            trip_responses, passenger_responses,
                            dashboard_url):
    """
    Sends a detailed HTML email confirmation via Resend.
    """
    try:
        resend.api_key = RESEND_API_KEY

        origin = trip_responses.get("origin", "")
        destination = trip_responses.get("destination", "")
        travel_date = trip_responses.get("travel_date", "")
        airline = chosen_offer.get("airline", "")
        departure = chosen_offer.get("departure_time", "")
        arrival = chosen_offer.get("arrival_time", "")
        duration = chosen_offer.get("duration", "")
        price = chosen_offer.get("price", "")
        cabin = trip_responses.get("cabin_class", "Economy")
        name = passenger_responses.get("full_name", "Traveler")

        html_body = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto;">
            <h2 style="color: #2c3e50;">✈️ Your Booking is Confirmed!</h2>

            <p>Hi {name},</p>
            <p>Your flight has been successfully booked. Here are your details:</p>

            <table style="width:100%; border-collapse: collapse;">
                <tr>
                    <td style="padding: 8px; font-weight: bold;">Booking ID</td>
                    <td style="padding: 8px;">{booking_id}</td>
                </tr>
                <tr style="background:#f2f2f2;">
                    <td style="padding: 8px; font-weight: bold;">Route</td>
                    <td style="padding: 8px;">{origin} → {destination}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; font-weight: bold;">Date</td>
                    <td style="padding: 8px;">{travel_date}</td>
                </tr>
                <tr style="background:#f2f2f2;">
                    <td style="padding: 8px; font-weight: bold;">Airline</td>
                    <td style="padding: 8px;">{airline}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; font-weight: bold;">Departure</td>
                    <td style="padding: 8px;">{departure}</td>
                </tr>
                <tr style="background:#f2f2f2;">
                    <td style="padding: 8px; font-weight: bold;">Arrival</td>
                    <td style="padding: 8px;">{arrival}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; font-weight: bold;">Duration</td>
                    <td style="padding: 8px;">{duration}</td>
                </tr>
                <tr style="background:#f2f2f2;">
                    <td style="padding: 8px; font-weight: bold;">Cabin Class</td>
                    <td style="padding: 8px;">{cabin}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; font-weight: bold;">Total Price</td>
                    <td style="padding: 8px;"><strong>{price}</strong></td>
                </tr>
            </table>

            <br>
            <p>
                <a href="{dashboard_url}/{booking_id}"
                   style="background:#2c3e50; color:white; padding:10px 20px;
                          text-decoration:none; border-radius:5px;">
                    View Booking on Dashboard
                </a>
            </p>

            <p style="color:#999; font-size:12px;">
                ⚠️ This is a demo booking. No real payment was charged.
            </p>
        </div>
        """

        params = {
            "from": RESEND_FROM_EMAIL,
            "to": [to_email],
            "subject": f"Booking Confirmed - {booking_id}",
            "html": html_body
        }

        response = resend.Emails.send(params)
        print("Email sent, ID:", response["id"])
        return True

    except Exception as e:
        print("Email error:", e)
        return False


# -----------------------------------------------------------------------
# Master function — call this after payment succeeds
# -----------------------------------------------------------------------
def complete_booking(db_conn_func, call_sid, chosen_offer,
                     trip_responses, passenger_responses,
                     payment_result, dashboard_url):
    """
    Orchestrates the full booking completion:
    1. Generates booking ID
    2. Saves booking record to Supabase
    3. Sends email confirmation via Resend
    4. Returns voice confirmation text + status flags
    """
    booking_id = generate_booking_id()

    # 1. Save to database
    save_booking_record(
        db_conn_func=db_conn_func,
        call_sid=call_sid,
        booking_id=booking_id,
        chosen_offer=chosen_offer,
        trip_responses=trip_responses,
        passenger_responses=passenger_responses,
        payment_result=payment_result
    )

    # 2. Send email confirmation
    email_sent = send_email_confirmation(
        to_email=passenger_responses.get("email", ""),
        booking_id=booking_id,
        chosen_offer=chosen_offer,
        trip_responses=trip_responses,
        passenger_responses=passenger_responses,
        dashboard_url=dashboard_url
    )

    # 3. Build voice confirmation text
    booking_letters = " ".join(list(booking_id))
    voice_text = (
        f"Your booking has been confirmed! "
        f"Your booking ID is {booking_letters}. "
    )

    if email_sent:
        voice_text += (
            "You will receive a confirmation email shortly with all your flight details. "
        )
    else:
        voice_text += (
            "Your booking is saved in our system. "
            "Please note down your booking ID. "
        )

    voice_text += "Thank you for using our AI flight booking service. Goodbye!"

    return {
        "booking_id": booking_id,
        "email_sent": email_sent,
        "voice_text": voice_text
    }