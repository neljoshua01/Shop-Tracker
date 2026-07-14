from dataclasses import dataclass, field


@dataclass
class Product:
    """
    Represents a Shopee product being monitored.
    """

    # Basic information
    url: str

    shop_id: str = ""
    item_id: str = ""

    name: str = "Unknown"

    # Pricing
    current_price: str = ""
    original_price: str = ""
    discount: str = ""

    previous_price: str = ""

    # Product information
    rating: str = ""
    sold: str = ""

    stock: str = ""

    shipping: list[str] = field(default_factory=list)
    vouchers: list[str] = field(default_factory=list)

    # Monitoring
    is_monitoring: bool = False