from dataclasses import dataclass

from purchase.models.product_reference import ProductReference
from purchase.models.trigger_condition import TriggerCondition
from purchase.models.payment_method import PaymentMethod

@dataclass(slots=True)
class PurchaseRequest:
    """
    Everything the user wants to buy.
    """

    reference: ProductReference

    options: dict[str, str]

    quantity: int = 1

    auto_checkout: bool = True

    target_price: int | None = None

    payment_method: PaymentMethod = PaymentMethod.SPAYLATER

    trigger: TriggerCondition = TriggerCondition.PRICE_TARGET

    polling_interval: int = 30

    lock_selected_variations: bool = True
