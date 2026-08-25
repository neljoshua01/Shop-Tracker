import json
from pathlib import Path

from models.product import Product
from purchase.models.product_info import ProductInfo
from purchase.models.purchase_profile import PurchaseProfile
from purchase.models.trigger_condition import TriggerCondition
from purchase.models.variation import Variation
from purchase.models.payment_method import PaymentMethod


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

        if self.settings_file.exists():

            with open(
                self.settings_file,
                "r",
                encoding="utf-8"
            ) as file:

                content = json.load(file)

            # Old format
            if isinstance(content, list):
                content = {}

        else:

            content = {}

        content["products"] = data

        with open(
            self.settings_file,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                content,
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

            content = json.load(file)

        # Old format (list)
        if isinstance(content, list):
            data = content

        # New format (dict)
        else:
            data = content.get("products", [])

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

    def save_purchase_profiles(self, profiles):
        content = self._read_content()
        content["purchase_profiles"] = [self._profile_to_dict(profile) for profile in profiles]
        self._write_content(content)

    def load_purchase_profiles(self):
        profiles = []
        for data in self._read_content().get("purchase_profiles", []):
            try:
                product_data = data["product"]
                variations = [Variation(**variation) for variation in product_data.get("available_variations", [])]
                product = ProductInfo(
                    item_id=product_data["item_id"], shop_id=product_data["shop_id"],
                    product_name=product_data["product_name"], shop_name=product_data["shop_name"],
                    product_url=product_data["product_url"], currency=product_data["currency"],
                    image=product_data["image"], available_variations=variations,
                )
                selected_ids = set(data.get("selected_model_ids", []))
                profiles.append(PurchaseProfile(
                    profile_name=data["profile_name"], product=product,
                    selected_variations=[v for v in variations if v.model_id in selected_ids],
                    quantity=data.get("quantity", 1), trigger=TriggerCondition(data.get("trigger", "track_only")),
                    target_price=data.get("target_price"), polling_interval=data.get("polling_interval", 30),
                    payment_method=PaymentMethod(data.get("payment_method", PaymentMethod.SPAYLATER.value)),
                    auto_checkout=data.get("auto_checkout", False),
                    lock_selected_variations=data.get("lock_selected_variations", True),
                ))
            except (KeyError, TypeError, ValueError):
                continue
        return profiles

    def _read_content(self):
        if not self.settings_file.exists():
            return {}
        with open(self.settings_file, "r", encoding="utf-8") as file:
            content = json.load(file)
        return {} if isinstance(content, list) else content

    def _write_content(self, content):
        with open(self.settings_file, "w", encoding="utf-8") as file:
            json.dump(content, file, indent=4)

    @staticmethod
    def _profile_to_dict(profile):
        return {
            "profile_name": profile.profile_name,
            "product": {
                "item_id": profile.product.item_id, "shop_id": profile.product.shop_id,
                "product_name": profile.product.product_name, "shop_name": profile.product.shop_name,
                "product_url": profile.product.product_url, "currency": profile.product.currency,
                "image": profile.product.image,
                "available_variations": [
                    {"model_id": v.model_id, "name": v.name, "options": v.options,
                     "price": v.price, "price_before_discount": v.price_before_discount,
                     "has_stock": v.has_stock, "tier_index": v.tier_index, "sku_image": v.sku_image}
                    for v in profile.product.available_variations
                ],
            },
            "selected_model_ids": [v.model_id for v in profile.selected_variations],
            "quantity": profile.quantity, "trigger": profile.trigger.value,
            "target_price": profile.target_price, "polling_interval": profile.polling_interval,
            "payment_method": profile.payment_method.value,
            "auto_checkout": profile.auto_checkout,
            "lock_selected_variations": profile.lock_selected_variations,
        }
