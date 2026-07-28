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

    image_url: str = ""

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

    # Auto-checkout
    target_price: float | None = None
    target_locked: bool = False
    auto_checkout: bool = False
    purchased: bool = False


    # Purchase Information
    purchase_reason: str = ""
    purchase_trigger_price: float | None = None
    purchase_detected_at: str = ""
    checkout_started_at: str = ""
    checkout_completed_at: str = ""