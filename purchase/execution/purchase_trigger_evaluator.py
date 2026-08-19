"""
Evaluates whether the current SKU state
should trigger the purchase pipeline.
"""

from purchase.models.purchase_session import PurchaseSession
from purchase.models.sku_price_state import SkuPriceState
from purchase.models.trigger_condition import TriggerCondition


class PurchaseTriggerEvaluator:

    def evaluate(
        self,
        session: PurchaseSession,
        state: SkuPriceState,
    ) -> bool:

        trigger = session.request.trigger

        if trigger is TriggerCondition.TRACK_ONLY:
            return False

        if trigger is TriggerCondition.STOCK_AVAILABLE:
            return state.has_stock

        target_price = session.request.target_price

        if target_price is None:

            print(
                "[PurchaseTriggerEvaluator] "
                "No target price configured."
            )

            return False

        #
        # Determine which price is currently valid
        # for purchase evaluation.
        #
        current_price = state.price

        if (
            state.deep_discount
            and state.promotion_event_status == "LIVE"
            and state.promotion_price is not None
            and state.promotion_price > 0
        ):

            current_price = state.promotion_price

            print(
                "[PurchaseTriggerEvaluator] "
                "LIVE deep discount detected."
            )

        print(
            "[PurchaseTriggerEvaluator] "
            f"Current price: {current_price}"
        )

        print(
            "[PurchaseTriggerEvaluator] "
            f"Target price: {target_price}"
        )

        price_reached = current_price <= target_price

        if trigger is TriggerCondition.PRICE_AND_STOCK:
            return price_reached and state.has_stock

        if price_reached:

            print(
                "[PurchaseTriggerEvaluator] "
                "TARGET REACHED."
            )

            return True

        print(
            "[PurchaseTriggerEvaluator] "
            "Target not reached."
        )

        return False
