"""
Coordinates the purchase workflow.
"""

from purchase.models.purchase_request import PurchaseRequest
from purchase.models.purchase_session import PurchaseSession
from purchase.models.purchase_status import PurchaseStatus
from purchase.services.product_loader import ProductLoader
from purchase.services.selection_resolver import SelectionResolver


class PurchaseService:

    def __init__(self):

        self.loader = ProductLoader()

        self.selection = SelectionResolver()

    def prepare(
        self,
        request: PurchaseRequest,
    ) -> PurchaseSession:
        """
        Loads the requested product and resolves
        the requested variation.

        Returns a PurchaseSession that will be
        used throughout the purchase workflow.
        """

        #
        # Load the product
        #
        product = self.loader.load(
            request.reference,
        )

        #
        # Resolve the requested variation
        #
        variation = self.selection.resolve(
            product,
            request.options,
        )

        if variation is None:

            raise ValueError(
                "Requested variation could not be found."
            )

        #
        # Build the runtime session
        #
        session = PurchaseSession(
            request=request,
            product=product,
            variation=variation,
        )

        session.status = PurchaseStatus.READY

        return session
