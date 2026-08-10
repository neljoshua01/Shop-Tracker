"""
Extracts the selected SKU pricing information
from a Shopee get_pc response.
"""

from purchase.models.sku_price_state import SkuPriceState


class SkuPriceParser:

    def parse(
        self,
        data: dict,
        model_id: int,
    ) -> SkuPriceState | None:

        try:

            item = data["data"]["item"]

        except (KeyError, TypeError):

            return None

        models = item.get("models", [])

        for model in models:

            if model.get("model_id") != model_id:
                continue

            price_stocks = model.get(
                "price_stocks",
                [],
            )

            promotion_types = tuple(
                stock.get("promotion_type")
                for stock in price_stocks
                if stock.get("promotion_type") is not None
            )

            return SkuPriceState(
                item_id=model["item_id"],
                model_id=model["model_id"],
                name=model.get("name", ""),
                price=model["price"],
                price_before_discount=model.get(
                    "price_before_discount"
                ),
                promotion_id=model.get(
                    "promotion_id"
                ),
                promotion_types=promotion_types,
            )

        return None