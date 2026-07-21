import customtkinter as ctk

from ui.components.product_card import ProductCard


class ProductList(ctk.CTkScrollableFrame):

    def __init__(
        self,
        master,
        stop_callback=None,
        **kwargs
    ):

        super().__init__(master, **kwargs)

        self.stop_callback = stop_callback

        #
        # Called whenever Auto Checkout / Target Price changes.
        #
        self.set_target_callback = None

        self.cards = {}

    # =====================================================
    # Add or Update Product
    # =====================================================

    def update_product(self, product):

        if product.url in self.cards:

            self.cards[product.url].update_data(product)
            return

        card = ProductCard(
            self,
            product,
            stop_callback=self.stop_callback,
            set_target_callback=self.set_target_callback
        )

        card.pack(
            fill="x",
            padx=10,
            pady=8
        )

        self.cards[product.url] = card

    # =====================================================
    # Remove Product
    # =====================================================

    def remove_product(self, url):

        card = self.cards.pop(url, None)

        if card:

            card.destroy()

    # =====================================================
    # Clear All
    # =====================================================

    def clear(self):

        for card in self.cards.values():
            card.destroy()

        self.cards.clear()

    # =====================================================
    # Count
    # =====================================================

    def count(self):

        return len(self.cards)