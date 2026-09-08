"""
Temporary test — confirms our Duffel direct API connection works.
Run with: python test_duffel_connection.py
Delete this file once confirmed working.
"""

import requests
from config import DUFFEL_API_KEY

url = "https://api.duffel.com/air/airlines"
headers = {
    "Authorization": f"Bearer {DUFFEL_API_KEY}",
    "Duffel-Version": "v2",
    "Accept": "application/json"
}

try:
    response = requests.get(url, headers=headers)
    data = response.json()
    airlines = data["data"][:5]
    print("Connection successful! Sample airlines from Duffel:")
    for airline in airlines:
        print("-", airline["name"])
except Exception as e:
    print("Connection failed:", e)