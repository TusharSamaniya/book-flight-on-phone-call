"""
Temporary test — confirms our Duffel client is set up correctly
and can successfully talk to Duffel's servers.

Run with: python test_duffel_connection.py
Delete this file once confirmed working.
"""

from flights import duffel

try:
    # Airlines is a simple, harmless read-only endpoint —
    # good for just checking our connection/auth works.
    airlines = duffel.airlines.list()
    first_five = list(airlines)[:5]
    print("Connection successful! Sample airlines from Duffel:")
    for airline in first_five:
        print("-", airline.name)
except Exception as e:
    print("Connection failed:", e)