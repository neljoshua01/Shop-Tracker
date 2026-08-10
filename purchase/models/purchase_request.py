from dataclasses import dataclass

from purchase.models.product_reference import ProductReference


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