"""
Extracts the selected SKU pricing and promotion information
from a Shopee get_pc response.
"""
import time
from purchase.models.sku_price_state import SkuPriceState


class SkuPriceParser:

    def parse(
        self,
        data: dict,
        model_id: int,
    ) -> SkuPriceState | None:

        try:
            payload = data["data"]
            item = payload["item"]

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

            #
            # ==========================================
            # Deep Discount / Promotion State
            # ==========================================
            #

            bottom_banner = payload.get(
                "bottom_banner"
            )

            if not isinstance(bottom_banner, dict):
                bottom_banner = {}

            deep_discount = bottom_banner.get(
                "deep_discount"
            )

            has_deep_discount = isinstance(
                deep_discount,
                dict,
            )

            promotion_id = None
            promotion_price = None
            promotion_skin = None
            promotion_reminder_event = None
            promotion_is_lpp = None

            if has_deep_discount:

                promotion_id = deep_discount.get(
                    "promotion_id"
                )

                promotion_is_lpp = deep_discount.get(
                    "is_lpp"
                )

                promotion_price_data = (
                    deep_discount.get(
                        "promotion_price"
                    )
                )

                if isinstance(
                    promotion_price_data,
                    dict,
                ):

                    promotion_price = (
                        promotion_price_data.get(
                            "single_value"
                        )
                    )

                promotion_skin = (
                    deep_discount.get(
                        "skin"
                    )
                )

                promotion_reminder_event = (
                    deep_discount.get(
                        "reminder_event"
                    )
                )

            #
            # ==========================================
            # Promotion Event State
            # ==========================================
            #

            promotion_event_status = (
                self.get_event_status(
                    promotion_reminder_event
                )
            )

            (
                seconds_until_start,
                seconds_until_end,
            ) = self.get_event_timing(
                promotion_reminder_event
            )

            return SkuPriceState(

                item_id=model["item_id"],

                model_id=model["model_id"],

                name=model.get(
                    "name",
                    "",
                ),

                price=model["price"],

                price_before_discount=model.get(
                    "price_before_discount"
                ),

                promotion_id=model.get(
                    "promotion_id"
                ),

                promotion_types=promotion_types,

                #
                # Promotion state
                #

                deep_discount=has_deep_discount,

                promotion_price=promotion_price,

                promotion_event_status=(
                    promotion_event_status
                ),

                promotion_seconds_until_start=(
                    seconds_until_start
                ),

                promotion_seconds_until_end=(
                    seconds_until_end
                ),

                promotion_skin=promotion_skin,

                promotion_reminder_event=(
                    promotion_reminder_event
                ),

                promotion_is_lpp=(
                    promotion_is_lpp
                ),

                has_stock=model.get("has_stock", False),
            )

        return None

    #
    # ==================================================
    # Promotion Event Helpers
    # ==================================================
    #

    def get_event_status(
        self,
        reminder_event,
    ):

        if not isinstance(
            reminder_event,
            dict,
        ):
            return "NO_EVENT"

        start_time = reminder_event.get(
            "start_time"
        )

        end_time = reminder_event.get(
            "end_time"
        )

        if start_time is None:
            return "NO_EVENT"

        #
        # Shopee timestamps are epoch seconds.
        #

        now = int(time.time())

        if now < start_time:
            return "UPCOMING"

        if end_time is not None and now >= end_time:
            return "ENDED"

        return "LIVE"

    def get_event_timing(
        self,
        reminder_event,
    ):

        if not isinstance(
            reminder_event,
            dict,
        ):
            return (
                None,
                None,
            )

        start_time = reminder_event.get(
            "start_time"
        )

        end_time = reminder_event.get(
            "end_time"
        )

        import time

        now = int(time.time())

        seconds_until_start = None
        seconds_until_end = None

        if start_time is not None:

            seconds_until_start = (
                int(start_time - now)
            )

        if end_time is not None:

            seconds_until_end = (
                int(end_time - now)
            )

        return (
            seconds_until_start,
            seconds_until_end,
        )
