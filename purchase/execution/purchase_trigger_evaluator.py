"""
Evaluates whether the current SKU state
should trigger the purchase pipeline.
"""

from purchase.models.purchase_session import PurchaseSession
from purchase.models.sku_price_state import SkuPriceState


class PurchaseTriggerEvaluator:

    def evaluate(
        self,
        session: PurchaseSession,
        state: SkuPriceState,
    ) -> bool:

        target_price = session.request.target_price

        if target_price is None:

            print(
                "[PurchaseTriggerEvaluator] "
                "No target price configured."
            )

            return False

        print(
            "[PurchaseTriggerEvaluator] "
            f"Current price: {state.price}"
        )

        print(
            "[PurchaseTriggerEvaluator] "
            f"Target price: {target_price}"
        )

        if state.price <= target_price:

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