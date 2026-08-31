"""
Isolated Discord purchase-notification renderer test.

This file intentionally contains BOTH the temporary notification data model and
renderer so the production application remains untouched while the notification
visuals are validated.

It performs NO Discord request and contains NO webhook handling.

Run from the repository root:

    python3 tests/test_discord_notification_renderer.py

Optional examples:

    python3 tests/test_discord_notification_renderer.py \
        --product-image /path/to/product.png \
        --output-dir tests/output/discord_notifications

Outputs:
    order_created_payment_required.png
    purchase_successful.png
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# Headless-safe Qt rendering. This only affects this isolated test process.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter, QPen


CANVAS_WIDTH = 1365
CANVAS_HEIGHT = 1080

BG = QColor("#06142c")
CARD = QColor("#081d3d")
CARD_2 = QColor("#0a2248")
BORDER = QColor("#2147b5")
TEXT = QColor("#f4f6ff")
MUTED = QColor("#86a6ef")
PURPLE = QColor("#9b4dff")
PURPLE_DARK = QColor("#5427b7")
ORANGE = QColor("#ff9b00")
ORANGE_BG = QColor("#351615")
GREEN = QColor("#42efc0")
GREEN_BG = QColor("#083c3f")
DIVIDER = QColor("#173e81")
STRIKE = QColor("#6e86bd")


@dataclass(slots=True)
class PurchaseNotificationData:
    """Test-only notification payload mirroring the validated purchase data."""

    product_name: str
    product_image: str | None
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


class NotificationCardRenderer:
    """Test-only renderer for the two approved notification mockup states."""

    def render_order_created(self, data: PurchaseNotificationData, output: Path) -> None:
        self._render(data, output, successful=False)

    def render_purchase_successful(self, data: PurchaseNotificationData, output: Path) -> None:
        self._render(data, output, successful=True)

    def _render(self, data: PurchaseNotificationData, output: Path, *, successful: bool) -> None:
        image = QImage(CANVAS_WIDTH, CANVAS_HEIGHT, QImage.Format.Format_ARGB32)
        image.fill(BG)

        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        self._draw_outer_frame(painter)
        self._draw_header(painter, data, successful)
        self._draw_status_banner(painter, successful)
        self._draw_product_card(painter, data)
        self._draw_details(painter, data)
        self._draw_timeline(painter, data, successful)
        self._draw_footer(painter)

        painter.end()
        output.parent.mkdir(parents=True, exist_ok=True)
        if not image.save(str(output), "PNG"):
            raise RuntimeError(f"Failed to save rendered notification: {output}")

    @staticmethod
    def _font(size: int, *, bold: bool = False) -> QFont:
        font = QFont("Arial")
        font.setPixelSize(size)
        font.setBold(bold)
        return font

    @staticmethod
    def _rounded_rect(painter: QPainter, rect: QRectF, fill: QColor, border: QColor, radius: float = 18) -> None:
        painter.setBrush(fill)
        painter.setPen(QPen(border, 2))
        painter.drawRoundedRect(rect, radius, radius)

    def _draw_outer_frame(self, painter: QPainter) -> None:
        self._rounded_rect(
            painter,
            QRectF(34, 28, CANVAS_WIDTH - 68, CANVAS_HEIGHT - 56),
            BG,
            QColor("#203bd1"),
            22,
        )

    def _draw_header(self, painter: QPainter, data: PurchaseNotificationData, successful: bool) -> None:
        # Shopee-style bag mark.
        bag = QRectF(78, 54, 72, 72)
        painter.setBrush(QColor("#ff5b35"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(bag, 12, 12)
        painter.setPen(QPen(TEXT, 5))
        painter.drawArc(QRectF(93, 41, 42, 40), 0, 180 * 16)
        painter.setFont(self._font(42, bold=True))
        painter.drawText(bag, Qt.AlignmentFlag.AlignCenter, "S")

        painter.setPen(TEXT)
        painter.setFont(self._font(31, bold=True))
        painter.drawText(QRectF(170, 51, 480, 40), Qt.AlignmentFlag.AlignVCenter, "Shopee Tracker")

        app_rect = QRectF(435, 54, 72, 34)
        self._rounded_rect(painter, app_rect, QColor("#5738e8"), QColor("#7457ff"), 9)
        painter.setPen(TEXT)
        painter.setFont(self._font(19, bold=True))
        painter.drawText(app_rect, Qt.AlignmentFlag.AlignCenter, "APP")

        painter.setPen(MUTED)
        painter.setFont(self._font(25))
        painter.drawText(QRectF(170, 92, 390, 34), Qt.AlignmentFlag.AlignVCenter, "Purchase Notification")

        stamp = (data.to_ship_at if successful and data.to_ship_at else data.order_created_at)
        stamp_text = stamp.strftime("%b %d, %Y  •  %I:%M %p").replace(" 0", " ")
        painter.setFont(self._font(22))
        painter.drawText(
            QRectF(870, 57, 405, 36),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            stamp_text,
        )

        painter.setPen(QPen(DIVIDER, 2))
        painter.drawLine(72, 142, CANVAS_WIDTH - 72, 142)

    def _draw_status_banner(self, painter: QPainter, successful: bool) -> None:
        rect = QRectF(72, 158, CANVAS_WIDTH - 144, 124)
        if successful:
            fill, border, accent = GREEN_BG, GREEN, GREEN
            title = "Purchase Successful!"
            subtitle = "Your item has been purchased and is now in To Ship."
            icon = "✓"
        else:
            fill, border, accent = ORANGE_BG, ORANGE, ORANGE
            title = "Order Created - Payment Required"
            subtitle = "Your order has been created. Please complete the payment to confirm."
            icon = "⌛"

        self._rounded_rect(painter, rect, fill, border, 18)

        circle = QRectF(100, 177, 82, 82)
        painter.setBrush(QColor(accent.red(), accent.green(), accent.blue(), 45))
        painter.setPen(QPen(accent, 4))
        painter.drawEllipse(circle)
        painter.setPen(accent)
        painter.setFont(self._font(46, bold=True))
        painter.drawText(circle, Qt.AlignmentFlag.AlignCenter, icon)

        painter.setPen(accent)
        painter.setFont(self._font(38, bold=True))
        painter.drawText(QRectF(210, 176, 940, 48), Qt.AlignmentFlag.AlignVCenter, title)
        painter.setPen(successful and QColor("#b3f8e3") or QColor("#ffb427"))
        painter.setFont(self._font(21))
        painter.drawText(QRectF(210, 225, 960, 34), Qt.AlignmentFlag.AlignVCenter, subtitle)

    def _draw_product_card(self, painter: QPainter, data: PurchaseNotificationData) -> None:
        rect = QRectF(72, 304, CANVAS_WIDTH - 144, 286)
        self._rounded_rect(painter, rect, CARD, BORDER, 18)

        image_rect = QRectF(96, 327, 292, 238)
        self._rounded_rect(painter, image_rect, QColor("#16163d"), PURPLE_DARK, 16)
        self._draw_product_image(painter, data.product_image, image_rect.adjusted(18, 18, -18, -18))

        badge = QRectF(420, 330, 150, 34)
        self._rounded_rect(painter, badge, PURPLE_DARK, PURPLE, 17)
        painter.setPen(TEXT)
        painter.setFont(self._font(18, bold=True))
        painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, "✓ Purchased")

        painter.setPen(TEXT)
        painter.setFont(self._font(31, bold=True))
        title_rect = QRectF(420, 375, 620, 80)
        painter.drawText(
            title_rect,
            Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
            data.product_name,
        )

        painter.setPen(MUTED)
        painter.setFont(self._font(21))
        painter.drawText(
            QRectF(420, 464, 650, 62),
            Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
            f"Variation: {data.variation}",
        )

        painter.setPen(PURPLE)
        painter.setFont(self._font(36, bold=True))
        painter.drawText(QRectF(420, 518, 260, 42), Qt.AlignmentFlag.AlignVCenter, self._peso(data.item_price))

        if data.discount_percent is not None:
            discount_rect = QRectF(685, 522, 120, 34)
            self._rounded_rect(painter, discount_rect, QColor("#064b42"), GREEN, 17)
            painter.setPen(GREEN)
            painter.setFont(self._font(18, bold=True))
            painter.drawText(discount_rect, Qt.AlignmentFlag.AlignCenter, f"{data.discount_percent}% OFF")

        if data.original_price is not None:
            old = self._peso(data.original_price)
            painter.setPen(STRIKE)
            painter.setFont(self._font(20))
            old_rect = QRectF(825, 523, 180, 34)
            painter.drawText(old_rect, Qt.AlignmentFlag.AlignVCenter, old)
            painter.setPen(QPen(STRIKE, 2))
            painter.drawLine(int(old_rect.left()), int(old_rect.center().y()), int(old_rect.left() + 120), int(old_rect.center().y()))

        painter.setPen(QColor("#ff5b35"))
        painter.setFont(self._font(27, bold=True))
        painter.drawText(QRectF(1080, 333, 155, 38), Qt.AlignmentFlag.AlignRight, "Shopee")
        painter.setPen(MUTED)
        painter.setFont(self._font(18))
        painter.drawText(QRectF(1050, 374, 185, 30), Qt.AlignmentFlag.AlignRight, data.shop_name)

    def _draw_product_image(self, painter: QPainter, path: str | None, rect: QRectF) -> None:
        if path:
            image = QImage(path)
            if not image.isNull():
                scaled = image.scaled(
                    int(rect.width()),
                    int(rect.height()),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                x = rect.x() + (rect.width() - scaled.width()) / 2
                y = rect.y() + (rect.height() - scaled.height()) / 2
                painter.drawImage(QRectF(x, y, scaled.width(), scaled.height()), scaled)
                return

        painter.setPen(MUTED)
        painter.setFont(self._font(20, bold=True))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "PRODUCT\nIMAGE")

    def _draw_details(self, painter: QPainter, data: PurchaseNotificationData) -> None:
        left = QRectF(72, 606, 600, 248)
        right = QRectF(692, 606, 601, 248)
        self._rounded_rect(painter, left, CARD_2, BORDER, 18)
        self._rounded_rect(painter, right, CARD_2, BORDER, 18)

        self._detail_row(painter, left, 24, "Shop", data.shop_name)
        self._detail_row(painter, left, 98, "Variation", data.variation)
        self._detail_row(painter, left, 172, "Quantity", f"{data.quantity} item" if data.quantity == 1 else f"{data.quantity} items")

        self._detail_row(painter, right, 24, "Order ID", str(data.order_id))
        self._detail_row(painter, right, 98, "Payment Method", data.payment_method)
        order_time = data.order_created_at.strftime("%b %d, %Y  •  %I:%M %p").replace(" 0", " ")
        self._detail_row(painter, right, 172, "Order Time", order_time)

    def _detail_row(self, painter: QPainter, card: QRectF, offset_y: float, label: str, value: str) -> None:
        y = card.y() + offset_y
        icon = QRectF(card.x() + 24, y, 48, 48)
        painter.setBrush(PURPLE_DARK)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(icon)
        painter.setPen(TEXT)
        painter.setFont(self._font(20, bold=True))
        painter.drawText(icon, Qt.AlignmentFlag.AlignCenter, "•")

        painter.setPen(MUTED)
        painter.setFont(self._font(18))
        painter.drawText(QRectF(card.x() + 90, y - 2, card.width() - 115, 24), Qt.AlignmentFlag.AlignVCenter, label)
        painter.setPen(TEXT)
        painter.setFont(self._font(20))
        painter.drawText(QRectF(card.x() + 90, y + 23, card.width() - 115, 28), Qt.AlignmentFlag.AlignVCenter, value)

        if offset_y < 170:
            painter.setPen(QPen(DIVIDER, 1))
            painter.drawLine(int(card.x() + 26), int(y + 61), int(card.right() - 26), int(y + 61))

    def _draw_timeline(self, painter: QPainter, data: PurchaseNotificationData, successful: bool) -> None:
        rect = QRectF(72, 874, CANVAS_WIDTH - 144, 118)
        self._rounded_rect(painter, rect, CARD, BORDER, 16)

        if successful:
            stages = [
                ("Order Placed", data.order_created_at),
                ("Payment Confirmed", data.payment_confirmed_at),
                ("To Ship", data.to_ship_at),
            ]
            x_positions = [135, 450, 775]
            for i, (label, stamp) in enumerate(stages):
                self._timeline_stage(painter, x_positions[i], 895, label, stamp)
                if i < len(stages) - 1:
                    painter.setPen(QPen(PURPLE, 2))
                    painter.drawLine(x_positions[i] + 180, 932, x_positions[i + 1] - 25, 932)

            painter.setPen(QPen(DIVIDER, 2))
            painter.drawLine(1020, 894, 1020, 972)
            painter.setPen(MUTED)
            painter.setFont(self._font(17))
            painter.drawText(QRectF(1050, 902, 210, 22), Qt.AlignmentFlag.AlignLeft, "Estimated Delivery")
            painter.setPen(TEXT)
            painter.setFont(self._font(18))
            painter.drawText(
                QRectF(1050, 932, 220, 30),
                Qt.AlignmentFlag.AlignLeft,
                data.estimated_delivery or "Pending",
            )
        else:
            self._timeline_stage(painter, 220, 895, "Change Detected", data.change_detected_at)
            painter.setPen(QPen(PURPLE, 2))
            painter.drawLine(445, 932, 780, 932)
            self._timeline_stage(painter, 810, 895, "Order Placed", data.order_created_at)

    def _timeline_stage(self, painter: QPainter, x: int, y: int, label: str, stamp: datetime | None) -> None:
        circle = QRectF(x, y, 54, 54)
        painter.setBrush(PURPLE)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(circle)
        painter.setPen(TEXT)
        painter.setFont(self._font(25, bold=True))
        painter.drawText(circle, Qt.AlignmentFlag.AlignCenter, "✓")
        painter.setPen(PURPLE)
        painter.setFont(self._font(18, bold=True))
        painter.drawText(QRectF(x + 72, y + 3, 210, 23), Qt.AlignmentFlag.AlignVCenter, label)
        painter.setFont(self._font(17))
        painter.drawText(
            QRectF(x + 72, y + 30, 180, 24),
            Qt.AlignmentFlag.AlignVCenter,
            stamp.strftime("%I:%M %p").lstrip("0") if stamp else "Pending",
        )

    def _draw_footer(self, painter: QPainter) -> None:
        painter.setPen(QPen(DIVIDER, 2))
        painter.drawLine(72, 1014, CANVAS_WIDTH - 72, 1014)
        painter.setPen(TEXT)
        painter.setFont(self._font(18, bold=True))
        painter.drawText(QRectF(94, 1028, 250, 28), Qt.AlignmentFlag.AlignVCenter, "▣  Shopee Tracker")
        painter.setPen(MUTED)
        painter.setFont(self._font(17))
        painter.drawText(QRectF(355, 1028, 360, 28), Qt.AlignmentFlag.AlignVCenter, "Automate  •  Monitor  •  Purchase")
        painter.drawText(
            QRectF(935, 1028, 330, 28),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            "Sent via Discord Webhook",
        )

    @staticmethod
    def _peso(value: float) -> str:
        return f"₱ {value:,.0f}" if float(value).is_integer() else f"₱ {value:,.2f}"


def parse_time(value: str | None, fallback: datetime) -> datetime:
    if not value:
        return fallback
    return datetime.fromisoformat(value)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render both Discord purchase notification templates.")
    parser.add_argument("--output-dir", default="tests/output/discord_notifications")
    parser.add_argument("--product-image", default=None, help="Optional local product image path.")
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
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    _app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])

    now = datetime.now()
    change_detected = parse_time(args.change_time, now)
    order_created = parse_time(args.order_time, now)
    payment_confirmed = parse_time(args.payment_time, now)
    to_ship = parse_time(args.to_ship_time, now)

    data = PurchaseNotificationData(
        product_name=args.product_name,
        product_image=args.product_image,
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

    output_dir = Path(args.output_dir)
    created_path = output_dir / "order_created_payment_required.png"
    success_path = output_dir / "purchase_successful.png"

    renderer = NotificationCardRenderer()
    renderer.render_order_created(data, created_path)
    renderer.render_purchase_successful(data, success_path)

    print("=" * 78)
    print("DISCORD NOTIFICATION RENDERER TEST")
    print("=" * 78)
    print("Mode      : TEST-ONLY / LOCAL IMAGE RENDER")
    print("Production: NOT IMPORTED / NOT MODIFIED")
    print("Discord   : NO WEBHOOK REQUEST SENT")
    print()
    print("DATA MODEL")
    print(f"  Product        : {data.product_name}")
    print(f"  Shop           : {data.shop_name}")
    print(f"  Variation      : {data.variation}")
    print(f"  Quantity       : {data.quantity}")
    print(f"  Item price     : {NotificationCardRenderer._peso(data.item_price)}")
    print(f"  Original price : {NotificationCardRenderer._peso(data.original_price) if data.original_price is not None else '<none>'}")
    print(f"  Discount       : {data.discount_percent}%" if data.discount_percent is not None else "  Discount       : <none>")
    print(f"  Order total    : {NotificationCardRenderer._peso(data.order_total)}")
    print(f"  Order ID       : {data.order_id}")
    print(f"  Checkout ID    : {data.checkout_id}")
    print(f"  Payment        : {data.payment_method}")
    print()
    print("RENDERED FILES")
    print(f"  Notification #1: {created_path.resolve()}")
    print(f"  Notification #2: {success_path.resolve()}")
    print()
    print("RESULT: PASS — BOTH TEST-ONLY NOTIFICATION IMAGES RENDERED")
    print("No Discord request was sent and no production application file was touched.")


if __name__ == "__main__":
    main()
