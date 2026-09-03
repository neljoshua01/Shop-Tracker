"""
Isolated Discord purchase-notification text and webhook delivery test.

TEST-ONLY FILE
==============
This file intentionally contains the temporary notification data model and
text formatter so the production application remains untouched while the
Discord notification content and delivery are validated.

The notification is now TEXT-ONLY. No Qt/PySide6, image renderer, or image
attachment is used. Discord receives two organized text messages:

  1. Order Created - Payment Required
  2. Purchase Successful

Discord delivery is opt-in and test-only. The webhook URL is NEVER stored in
this repository. Supply it through DISCORD_WEBHOOK_URL or --webhook-url.

Run from the repository root:

    python3 tests/test_discord_notification_renderer.py

Send both test notifications to Discord:

    DISCORD_WEBHOOK_URL='https://discord.com/api/webhooks/...' \\
    python3 tests/test_discord_notification_renderer.py --send-discord

The file name is retained for compatibility with the existing isolated test,
but it is now a text-notification test rather than an image-renderer test.
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from datetime import datetime

import requests


@dataclass(slots=True)
class PurchaseNotificationData:
    """Test-only notification payload based on the validated purchase data."""

    product_name: str
    shop_name: str
    variation: str
    quantity: int
    item_price: float
    original_price: float | None
    order_total: float
    order_id: int
    checkout_id: int | None
    payment_method: str
    change_detected_at: datetime
    order_created_at: datetime
    payment_confirmed_at: datetime | None = None
    to_ship_at: datetime | None = None
    estimated_delivery: str | None = None

    @property
    def discount_percent(self) -> int | None:
        if self.original_price is None or self.original_price <= 0:
            return None
        if self.item_price >= self.original_price:
            return 0
        return round((1 - self.item_price / self.original_price) * 100)


class DiscordNotificationFormatter:
    """Test-only formatter for the two approved Discord notification states."""

    @staticmethod
    def _peso(value: float | None) -> str:
        if value is None:
            return "N/A"
        return f"₱{value:,.0f}" if float(value).is_integer() else f"₱{value:,.2f}"

    @staticmethod
    def _timestamp(value: datetime | None) -> str:
        if value is None:
            return "Pending"
        return value.strftime("%b %d, %Y • %I:%M %p").replace(" 0", " ")

    def order_created(self, data: PurchaseNotificationData) -> str:
        """Format notification #1: order exists and payment is still required."""
        discount = (
            f"{data.discount_percent}% OFF"
            if data.discount_percent is not None
            else "N/A"
        )

        return "\n".join(
            [
                "🛒 **SHOPEE TRACKER — ORDER CREATED**",
                "",
                "**⚠️ Payment Required**",
                "Your monitored product has been successfully placed as an order.",
                "Please complete the payment to continue the purchase.",
                "",
                "**PRODUCT**",
                f"• Product: {data.product_name}",
                f"• Shop: {data.shop_name}",
                f"• Variation: {data.variation}",
                f"• Quantity: {data.quantity}",
                "",
                "**PRICE**",
                f"• Item Price: {self._peso(data.item_price)}",
                f"• Original Price: {self._peso(data.original_price)}",
                f"• Discount: {discount}",
                f"• Order Total: {self._peso(data.order_total)}",
                "",
                "**ORDER**",
                f"• Order ID: `{data.order_id}`",
                f"• Checkout ID: `{data.checkout_id if data.checkout_id is not None else 'N/A'}`",
                f"• Payment Method: {data.payment_method}",
                f"• Order Time: {self._timestamp(data.order_created_at)}",
                "",
                "**TRACKER TIMELINE**",
                f"• Change Detected: {self._timestamp(data.change_detected_at)}",
                f"• Order Placed: {self._timestamp(data.order_created_at)}",
                "• Payment: Pending",
                "• To Ship: Pending",
            ]
        )

    def purchase_successful(self, data: PurchaseNotificationData) -> str:
        """Format notification #2: the exact paid order reached To Ship."""
        discount = (
            f"{data.discount_percent}% OFF"
            if data.discount_percent is not None
            else "N/A"
        )

        return "\n".join(
            [
                "🎉 **SHOPEE TRACKER — PURCHASE SUCCESSFUL**",
                "",
                "**✅ Purchase Successful**",
                "The exact paid order has been confirmed in the To Ship state.",
                "",
                "**PRODUCT**",
                f"• Product: {data.product_name}",
                f"• Shop: {data.shop_name}",
                f"• Variation: {data.variation}",
                f"• Quantity: {data.quantity}",
                "",
                "**PRICE**",
                f"• Item Price: {self._peso(data.item_price)}",
                f"• Original Price: {self._peso(data.original_price)}",
                f"• Discount: {discount}",
                f"• Order Total: {self._peso(data.order_total)}",
                "",
                "**ORDER**",
                f"• Order ID: `{data.order_id}`",
                f"• Checkout ID: `{data.checkout_id if data.checkout_id is not None else 'N/A'}`",
                f"• Payment Method: {data.payment_method}",
                f"• Order Time: {self._timestamp(data.order_created_at)}",
                "",
                "**TRACKER TIMELINE**",
                f"• Change Detected: {self._timestamp(data.change_detected_at)}",
                f"• Order Placed: {self._timestamp(data.order_created_at)}",
                f"• Payment Confirmed: {self._timestamp(data.payment_confirmed_at)}",
                f"• To Ship: {self._timestamp(data.to_ship_at)}",
                f"• Estimated Delivery: {data.estimated_delivery or 'Pending'}",
            ]
        )


class DiscordWebhookSender:
    """Test-only Discord webhook sender for formatted text notifications."""

    def __init__(self, webhook_url: str, *, timeout: float = 30.0) -> None:
        self.webhook_url = webhook_url.strip()
        self.timeout = timeout
        self._validate_url()

    def _validate_url(self) -> None:
        from urllib.parse import urlparse

        parsed = urlparse(self.webhook_url)
        if parsed.scheme != "https" or parsed.netloc not in {"discord.com", "discordapp.com"}:
            raise ValueError("Webhook URL must be an HTTPS Discord webhook URL.")
        if not parsed.path.startswith("/api/webhooks/"):
            raise ValueError("Webhook URL does not look like a Discord webhook endpoint.")

    def send(self, content: str) -> None:
        if not content.strip():
            raise ValueError("Discord notification content cannot be empty.")

        payload = {
            "content": content,
            "username": "Shopee Tracker Test",
        }
        response = requests.post(
            self.webhook_url,
            json=payload,
            timeout=self.timeout,
        )

        if response.status_code not in (200, 204):
            body = response.text[:500]
            raise RuntimeError(
                f"Discord webhook failed with HTTP {response.status_code}: {body}"
            )


def parse_time(value: str | None, fallback: datetime) -> datetime:
    if not value:
        return fallback
    return datetime.fromisoformat(value)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Format and optionally deliver both Discord purchase notifications."
    )
    parser.add_argument(
        "--product-name",
        default="5M Kinesiology Tape Muscle Bandage Sports Cotton Elastic Adhesive Strain Injury Tape Pain Relief",
    )
    parser.add_argument("--shop-name", default="Nice Everyday")
    parser.add_argument("--variation", default="black,5cm*5m")
    parser.add_argument("--quantity", type=int, default=1)
    parser.add_argument("--item-price", type=float, default=99.0)
    parser.add_argument("--original-price", type=float, default=198.0)
    parser.add_argument("--order-total", type=float, default=183.0)
    parser.add_argument("--order-id", type=int, default=241876645202841)
    parser.add_argument("--checkout-id", type=int, default=241876645204503)
    parser.add_argument("--payment-method", default="SPayLater")
    parser.add_argument("--change-time", default=None, help="ISO datetime, e.g. 2026-08-31T20:55:00")
    parser.add_argument("--order-time", default=None, help="ISO datetime")
    parser.add_argument("--payment-time", default=None, help="ISO datetime")
    parser.add_argument("--to-ship-time", default=None, help="ISO datetime")
    parser.add_argument("--estimated-delivery", default="Sep 05 – Sep 15, 2026")
    parser.add_argument(
        "--send-discord",
        action="store_true",
        help="Send the two test text notifications through the webhook.",
    )
    parser.add_argument(
        "--webhook-url",
        default=None,
        help="Discord webhook URL; prefer DISCORD_WEBHOOK_URL instead.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    now = datetime.now()
    change_detected = parse_time(args.change_time, now)
    order_created = parse_time(args.order_time, now)
    payment_confirmed = parse_time(args.payment_time, now)
    to_ship = parse_time(args.to_ship_time, now)

    data = PurchaseNotificationData(
        product_name=args.product_name,
        shop_name=args.shop_name,
        variation=args.variation,
        quantity=args.quantity,
        item_price=args.item_price,
        original_price=args.original_price,
        order_total=args.order_total,
        order_id=args.order_id,
        checkout_id=args.checkout_id,
        payment_method=args.payment_method,
        change_detected_at=change_detected,
        order_created_at=order_created,
        payment_confirmed_at=payment_confirmed,
        to_ship_at=to_ship,
        estimated_delivery=args.estimated_delivery,
    )

    formatter = DiscordNotificationFormatter()
    notification_1 = formatter.order_created(data)
    notification_2 = formatter.purchase_successful(data)

    print("=" * 78)
    print("DISCORD NOTIFICATION TEXT + WEBHOOK TEST")
    print("=" * 78)
    print("Mode      : TEST-ONLY / TEXT NOTIFICATION")
    print("Production: NOT IMPORTED / NOT MODIFIED")
    print(f"Discord   : {'DELIVERY ENABLED' if args.send_discord else 'NO WEBHOOK REQUEST SENT'}")
    print()
    print("DATA MODEL")
    print(f"  Product        : {data.product_name}")
    print(f"  Shop           : {data.shop_name}")
    print(f"  Variation      : {data.variation}")
    print(f"  Quantity       : {data.quantity}")
    print(f"  Item price     : {formatter._peso(data.item_price)}")
    print(f"  Original price : {formatter._peso(data.original_price)}")
    print(f"  Discount       : {data.discount_percent}%" if data.discount_percent is not None else "  Discount       : N/A")
    print(f"  Order total    : {formatter._peso(data.order_total)}")
    print(f"  Order ID       : {data.order_id}")
    print(f"  Checkout ID    : {data.checkout_id}")
    print(f"  Payment        : {data.payment_method}")
    print()
    print("NOTIFICATION #1 — ORDER CREATED")
    print("-" * 78)
    print(notification_1)
    print()
    print("NOTIFICATION #2 — PURCHASE SUCCESSFUL")
    print("-" * 78)
    print(notification_2)

    if args.send_discord:
        webhook_url = args.webhook_url or os.getenv("DISCORD_WEBHOOK_URL")
        if not webhook_url:
            raise SystemExit(
                "--send-discord requires DISCORD_WEBHOOK_URL or --webhook-url."
            )

        sender = DiscordWebhookSender(webhook_url)
        print()
        print("DISCORD DELIVERY")
        print("  Sending notification #1...")
        sender.send(notification_1)
        print("  Notification #1: HTTP success")
        print("  Sending notification #2...")
        sender.send(notification_2)
        print("  Notification #2: HTTP success")
        print()
        print("RESULT: PASS — BOTH TEXT NOTIFICATIONS DELIVERED TO DISCORD")
    else:
        print()
        print("RESULT: PASS — BOTH TEST-ONLY TEXT NOTIFICATIONS FORMATTED")
        print("No Discord request was sent and no production application file was touched.")


if __name__ == "__main__":
    main()
