"""
This module contains constant values used across the application, such as
lists of known terms for pre-processing.
"""

# A list of known payment aggregator names.
# This list is used to strip these terms from the raw merchant string
# before processing. The terms should be in uppercase.
PAYMENT_AGGREGATORS = [
    "PAYPAL",
    "OPENPAY",
    "PAYTM",
    "RAZORPAY",
    "PHONEPE",
    "GOOGLE PAY",
    "G PAY",
    "SQUARE",
    "STRIPE",
    "UBER EATS",
    "SWIGGY",
    "ZOMATO",
]