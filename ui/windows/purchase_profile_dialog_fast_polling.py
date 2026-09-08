"""Purchase Profile dialog variant with a 1-second polling option.

The base dialog owns the purchase-profile workflow. This thin UI wrapper only
extends its polling choices so the high-frequency event setting is available
without changing the existing default of 30 seconds.
"""

from ui.windows.purchase_profile_dialog import PurchaseProfileDialog as _BasePurchaseProfileDialog


class PurchaseProfileDialog(_BasePurchaseProfileDialog):
    """Purchase Profile dialog with 1-second polling available."""

    POLLING_OPTIONS = [
        "1 second",
        "5 seconds",
        "10 seconds",
        "30 seconds",
        "60 seconds",
    ]

    def _build_settings(self):
        super()._build_settings()
        self.polling_menu.configure(values=self.POLLING_OPTIONS)
        self.polling_menu.set("30 seconds")
