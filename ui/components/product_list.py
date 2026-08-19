import customtkinter as ctk

from ui.components.product_card import ProductCard
from ui import colors, fonts


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
        self.empty_state = ctk.CTkFrame(
            self,
            fg_color=colors.SURFACE,
            corner_radius=8
        )

        self.empty_icon = ctk.CTkLabel(
            self.empty_state,
            text="▣",
            font=(fonts.FONT_FAMILY, 28),
            text_color=colors.TEXT_MUTED
        )

        self.empty_icon.pack(
            pady=(28, 8)
        )

        self.empty_title = ctk.CTkLabel(
            self.empty_state,
            text="No products being monitored",
            font=fonts.SUBTITLE,
            text_color=colors.TEXT_PRIMARY
        )

        self.empty_title.pack()

        self.empty_description = ctk.CTkLabel(
            self.empty_state,
            text="Add a Shopee product above to start monitoring its price and stock.",
            font=fonts.BODY,
            text_color=colors.TEXT_SECONDARY
        )

        self.empty_description.pack(
            pady=(5, 28)
        )

        self.empty_state.pack(
            fill="x",
            padx=4,
            pady=4
        )

    # =====================================================
    # Add or Update Product
    # =====================================================

    def update_product(self, product):

        self.empty_state.pack_forget()

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

        if not self.cards:
            self.empty_state.pack(
                fill="x",
                padx=4,
                pady=4
            )

    # =====================================================
    # Clear All
    # =====================================================

    def clear(self):

        for card in self.cards.values():
            card.destroy()

        self.cards.clear()

        self.empty_state.pack(
            fill="x",
            padx=4,
            pady=4
        )

    # =====================================================
    # Count
    # =====================================================

    def count(self):

        return len(self.cards)