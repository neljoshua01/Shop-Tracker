class CheckoutEngine:

    def should_checkout(self, product):

        #
        # Auto checkout disabled
        #
        if not product.auto_checkout:
            return False

        #
        # No target price
        #
        if product.target_price is None:
            return False

        #
        # Already purchased
        #
        if product.purchased:
            return False

        #
        # No current price yet
        #
        if not product.current_price:
            return False

        #
        # Convert current price
        #
        try:
            current = (
                str(product.current_price)
                .replace("₱", "")
                .replace(",", "")
                .strip()
            )

            current = float(current)

        except ValueError:
            return False

        #
        # Target reached
        #
        if current <= product.target_price:

            print("[CheckoutEngine] Target reached.")

            return True

        return False

    # =====================================================
    # DRY RUN
    # =====================================================

    async def buy(self, product):

        print()
        print("=" * 60)
        print("AUTO CHECKOUT (DRY RUN)")
        print("=" * 60)
        print(f"Product : {product.name}")
        print(f"Current : {product.current_price}")
        print(f"Target  : {product.target_price}")
        print()
        print("A REAL CHECKOUT WOULD START HERE")
        print("=" * 60)
        print()

        #
        # Prevent another trigger
        #
        product.purchased = True

        return True