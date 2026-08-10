from purchase.models.product_info import ProductInfo
from purchase.models.variation import Variation


class SelectionResolver:

    def resolve(
        self,
        product: ProductInfo,
        requested_options: dict[str, str],
    ) -> Variation | None:
        """
        Returns the variation that matches the requested options.
        """

        for variation in product.available_variations:

            if variation.options == requested_options:
                return variation

        return None