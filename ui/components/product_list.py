import customtkinter as ctk

from ui.components.product_card import ProductCard
from ui import colors, fonts


class ProductList(ctk.CTkScrollableFrame):
    def __init__(self, master, stop_callback=None, **kwargs):
        super().__init__(master, **kwargs)

        self.stop_callback = stop_callback
        self.set_target_callback = None
        self.cards = {}

        self.header = ctk.CTkFrame(
            self,
            fg_color=colors.SURFACE,
            border_width=1,
            border_color=colors.DIVIDER,
            corner_radius=6,
            height=34
        )
        self.header.pack(fill="x", padx=4, pady=(4, 3))
        self.header.pack_propagate(False)

        columns = [
            "Product", "Stock", "Auto Checkout", "Target Price",
            "Current Price", "Last Checked", "Actions"
        ]
        for index, label in enumerate(columns):
            ctk.CTkLabel(
                self.header,
                text=label,
                font=fonts.SMALL_BOLD,
                text_color=colors.TEXT_MUTED,
                anchor="w"
            ).grid(
                row=0,
                column=index,
                sticky="w",
                padx=(10 if index == 0 else 6, 4)
            )

        self.empty_state = ctk.CTkFrame(
            self,
            fg_color=colors.SURFACE,
            border_width=1,
            border_color=colors.DIVIDER,
            corner_radius=8,
            height=180
        )
        self.empty_state.pack_propagate(False)

        ctk.CTkFrame(
            self.empty_state,
            width=3,
            height=38,
            fg_color=colors.INFO,
            corner_radius=2
        ).pack(pady=(25, 8))

        self.empty_icon = ctk.CTkLabel(
            self.empty_state,
            text="▣",
            font=(fonts.FONT_FAMILY, 26),
            text_color=colors.INFO
        )
        self.empty_icon.pack(pady=(0, 7))

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
        self.empty_description.pack(pady=(4, 0))

        self.empty_state.pack(fill="x", padx=4, pady=3)

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
        card.pack(fill="x", padx=4, pady=3)
        self.cards[product.url] = card

    def remove_product(self, url):
        card = self.cards.pop(url, None)
        if card:
            card.destroy()

        if not self.cards:
            self.empty_state.pack(fill="x", padx=4, pady=3)

    def clear(self):
        for card in self.cards.values():
            card.destroy()
        self.cards.clear()
        self.empty_state.pack(fill="x", padx=4, pady=3)

    def count(self):
        return len(self.cards)
