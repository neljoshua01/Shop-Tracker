import json
from pathlib import Path

from models.product import Product


class SettingsService:

    def __init__(self):

        self.settings_file = Path("settings.json")

    # =====================================================
    # Save Products
    # =====================================================

    def save_products(self, products):

        data = []

        for product in products:

            data.append({
                "url": product.url,
                "shop_id": product.shop_id,
                "item_id": product.item_id,
                "name": product.name,
                "auto_checkout": product.auto_checkout,
                "target_price": product.target_price,
                "target_locked": getattr(product, "target_locked", False),
                "purchased": product.purchased
            })

        with open(
            self.settings_file,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                data,
                file,
                indent=4
            )
        print(f"[SettingsService] Saved to {self.settings_file.resolve()}")
    # =====================================================
    # Load Products
    # =====================================================

    def load_products(self):

        if not self.settings_file.exists():
            return []

        with open(
            self.settings_file,
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(file)

        products = []

        for item in data:

            product = Product(
                url=item["url"]
            )

            product.shop_id = item.get("shop_id", "")
            product.item_id = item.get("item_id", "")
            product.name = item.get("name", "Unknown")

            product.auto_checkout = item.get(
                "auto_checkout",
                False
            )

            product.target_price = item.get(
                "target_price"
            )

            product.target_locked = item.get(
                "target_locked",
                False
            )

            product.purchased = item.get(
                "purchased",
                False
            )

            products.append(product)

        return products