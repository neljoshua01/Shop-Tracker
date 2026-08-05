from purchase.models.product_info import ProductInfo
from purchase.models.variation import Variation


class ShopeeAPIParser:

    def parse(
        self,
        data,
    ):
        """
        Converts a Shopee Product API response into a ProductInfo object.
        """

        if "data" not in data:
            raise ValueError(
                "Missing 'data' section in Shopee response."
            )

        if "item" not in data["data"]:
            raise ValueError(
                "Missing 'item' section in Shopee response."
            )

        item = data["data"]["item"]

        product = self._parse_product(
            item,
        )

        product.available_variations = (
            self._parse_variations(item)
        )

        return product

    def _parse_product(
        self,
        item,
    ):
        """
        Builds the ProductInfo object from Shopee's item payload.
        """

        return ProductInfo(
            item_id=item["item_id"],
            shop_id=item["shop_id"],

            product_name=item["title"],

            shop_name=self._get_shop_name(
                item,
            ),

            product_url=item.get(
                "share_link",
                "",
            ),

            currency=item.get(
                "currency",
                "",
            ),

            image=self._get_product_image(
                item,
            ),
        )
    
    def _get_shop_name(
        self,
        item,
    ):
        """
        Returns the shop name from the Shopee API response.
        """

        return item.get(
            "shop_name",
            "",
        )


    def _get_product_image(
        self,
        item,
    ):
        """
        Returns the primary product image.
        """

        return item.get(
            "image",
            "",
        )

    def _parse_variations(
        self,
        item,
    ):
        """
        Converts Shopee models into Variation objects.
        """

        variations = []

        models = item.get(
            "models",
            [],
        )

        tier_variations = item.get(
            "tier_variations",
            [],
        )

        for model in models:

            variation = Variation(

                model_id=model["model_id"],

                name=self._build_variation_name(
                    model,
                    tier_variations,
                ),

                price=self._convert_price(
                    model["price"]
                ),

                price_before_discount=self._convert_price(
                    model["price_before_discount"]
                ),

                has_stock=model["has_stock"],

                tier_index=model.get(
                    "extinfo",
                    {},
                ).get(
                    "tier_index",
                    [],
                ),

                sku_image=(
                    model.get(
                        "extinfo",
                        {},
                    ).get(
                        "sku_image",
                        ""
                    )
                    or item.get(
                        "image",
                        ""
                    )
                ),
            )

            variations.append(
                variation
            )

        return variations
    
    def _build_variation_name(
        self,
        model,
        tier_variations,
    ):
        """
        Builds a human-readable variation name from Shopee's
        tier_index information.
        """

        tier_index = model.get(
            "extinfo",
            {},
        ).get(
            "tier_index",
            [],
        )

        selected_options = []

        for option_index, tier in zip(
            tier_index,
            tier_variations,
        ):

            options = tier.get(
                "options",
                [],
            )

            if (
                option_index is None
                or option_index < 0
                or option_index >= len(options)
            ):
                continue

            selected_options.append(
                options[option_index]
            )

        return " / ".join(
            selected_options
        )

    def _convert_price(
        self,
        value,
    ):
        """
        Converts Shopee's integer price into a decimal value.
        """

        if value is None:
            return 0.0

        return float(value) / 100000