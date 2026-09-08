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