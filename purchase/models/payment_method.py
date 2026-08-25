from enum import Enum


class PaymentMethod(str, Enum):
    SPAYLATER = "SPayLater"
    CASH_ON_DELIVERY = "Cash on Delivery"