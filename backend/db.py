import json
import psycopg2
from config import DATABASE_URL


def get_connection():
    return psycopg2.connect(DATABASE_URL)


def create_session(call_sid, caller_number):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO sessions (call_sid, caller_number, current_step, responses)
        VALUES (%s, %s, %s, %s)
        """,
        (call_sid, caller_number, 0, json.dumps({}))
    )
    conn.commit()
    cur.close()
    conn.close()


def get_session(call_sid):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT current_step, responses FROM sessions WHERE call_sid = %s",
        (call_sid,)
    )
    row = cur.fetchone()
    cur.close()
    conn.close()

    if row is None:
        return None

    current_step, responses = row
    return {"step": current_step, "responses": responses}


def update_session(call_sid, step, responses, offers=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE sessions
        SET current_step = %s, responses = %s, offers = %s
        WHERE call_sid = %s
        """,
        (step, json.dumps(responses), json.dumps(offers or []), call_sid)
    )
    conn.commit()
    cur.close()
    conn.close()

def save_chosen_flight(call_sid, chosen_offer):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE sessions
        SET chosen_offer = %s
        WHERE call_sid = %s
        """,
        (json.dumps(chosen_offer), call_sid)
    )
    conn.commit()
    cur.close()
    conn.close()


def get_offers_from_session(call_sid):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT offers FROM sessions WHERE call_sid = %s",
        (call_sid,)
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row[0] if row else []

def save_passenger_info(call_sid, passenger_data):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO passengers
            (session_call_sid, full_name, phone, email, loyalty_number)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (
            call_sid,
            passenger_data["full_name"],
            passenger_data["phone"],
            passenger_data["email"],
            passenger_data.get("loyalty_number")
        )
    )
    conn.commit()
    cur.close()
    conn.close()


def mark_session_ready_for_payment(call_sid):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE sessions SET current_step = 'ready_for_payment' WHERE call_sid = %s",
        (call_sid,)
    )
    conn.commit()
    cur.close()
    conn.close()

def save_payment(call_sid, order_id, payment_id, amount, currency, status):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO payments
            (call_sid, order_id, payment_id, amount, currency, status)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (call_sid, order_id, payment_id, amount, currency, status)
    )
    conn.commit()
    cur.close()
    conn.close()


def get_chosen_offer_from_session(call_sid):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT chosen_offer FROM sessions WHERE call_sid = %s",
        (call_sid,)
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row[0] if row else None