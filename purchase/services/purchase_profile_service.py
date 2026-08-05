"""
Purchase profile validation service.
"""

from purchase.models.purchase_profile import PurchaseProfile
from purchase.models.trigger_condition import TriggerCondition


class PurchaseProfileService:
    """
    Business rules for purchase profiles.
    """

    @staticmethod
    def validate(profile: PurchaseProfile) -> None:
        """
        Raises ValueError when the profile is invalid.
        """

        if profile.quantity < 1:
            raise ValueError("Quantity must be at least 1.")

        if profile.polling_interval < 5:
            raise ValueError("Polling interval must be at least 5 seconds.")

        if (
            profile.trigger
            in (
                TriggerCondition.PRICE_TARGET,
                TriggerCondition.PRICE_AND_STOCK,
            )
            and profile.target_price is None
        ):
            raise ValueError(
                "Target price is required for the selected trigger."
            )