import razorpay
from config import RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET

# Initialize Razorpay client with our test mode credentials
client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))


def parse_amount_to_paise(price_string):
    """
    Converts a Duffel price string like "INR 45000.00" into
    the integer amount in paise that Razorpay expects.
    e.g. "INR 45000.00" → 4500000 (paise)
    e.g. "USD 550.00"   → 55000  (paise equivalent, kept as-is for demo)

    Razorpay always works in the smallest currency unit:
    - INR → paise (1 rupee = 100 paise)
    - USD → cents (1 dollar = 100 cents)
    """
    try:
        parts = price_string.strip().split()
        currency = parts[0].upper()
        amount_float = float(parts[1])
        amount_in_smallest_unit = int(amount_float * 100)
        return currency, amount_in_smallest_unit
    except Exception as e:
        print("Amount parsing error:", e)
        # Default fallback: ₹1 (100 paise) for demo safety
        return "INR", 100


def create_payment_order(chosen_offer):
    """
    Creates a Razorpay order using the flight price from our
    chosen Duffel offer. Returns the full order object on success,
    or None on failure.

    In test mode, this generates a real order ID that looks exactly
    like a production one — but no actual money is involved.
    """
    try:
        price_string = chosen_offer.get("price", "INR 1.00")
        currency, amount_paise = parse_amount_to_paise(price_string)

        order_data = {
            "amount": amount_paise,
            "currency": currency,
            "payment_capture": 1,   # auto-capture payment immediately on success
            "notes": {
                "airline": chosen_offer.get("airline", ""),
                "departure": chosen_offer.get("departure_time", ""),
                "demo": "true"
            }
        }

        order = client.order.create(data=order_data)
        print("Razorpay order created:", order["id"])
        return order

    except Exception as e:
        print("Razorpay order creation error:", e)
        return None


def simulate_payment_success(order_id):
    """
    In a real web app, the user would enter card details on a
    Razorpay checkout page. On a phone call demo, we simulate
    a successful payment automatically since the user can't
    type a card number during a voice call.

    This function simply returns a simulated payment result
    matching the structure Razorpay would normally return.
    """
    return {
        "order_id": order_id,
        "payment_id": f"pay_DEMO_{order_id[-8:]}",
        "status": "success"
    }