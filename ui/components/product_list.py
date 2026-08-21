import customtkinter as ctk

from ui.components.product_card import ProductCard
from ui import colors, fonts


class ProductList(ctk.CTkScrollableFrame):
    def __init__(self, master, stop_callback=None, **kwargs):
        super().__init__(master, **kwargs)

        self.stop_callback = stop_callback
        self.set_target_callback = None
        self.cards = {}

        # =====================================================
        # Product Table Header
        # =====================================================

        self.header = ctk.CTkFrame(
            self,
            fg_color=colors.SURFACE,
            border_width=1,
            border_color=colors.DIVIDER,
            corner_radius=6,
            height=44,
        )

        self.header.pack(
            fill="x",
            padx=4,
            pady=(4, 5),
        )

        self.header.pack_propagate(False)

        columns = [
            "Product",
            "Stock",
            "Auto Checkout",
            "Target Price",
            "Current Price",
            "Last Checked",
            "Actions",
        ]

        # Keep Product dominant without creating excessive
        # spacing between Product and Stock.
        weights = [4, 2, 2, 2, 2, 2, 1]

        # =====================================================
        # Header Inner Content
        # =====================================================

        # The header itself owns the border.
        # This transparent container keeps the labels away
        # from that border and provides consistent vertical
        # and horizontal breathing room.
        header_content = ctk.CTkFrame(
            self.header,
            fg_color="transparent",
        )

        header_content.pack(
            fill="both",
            expand=True,
            padx=8,
            pady=6,
        )

        # =====================================================
        # Header Column Configuration
        # =====================================================

        for index, weight in enumerate(weights):
            header_content.grid_columnconfigure(
                index,
                weight=weight,
            )

        header_content.grid_rowconfigure(
            0,
            weight=1,
        )

        # =====================================================
        # Header Labels
        # =====================================================

        for index, label in enumerate(columns):
            ctk.CTkLabel(
                header_content,
                text=label,
                font=fonts.SMALL_BOLD,
                text_color=colors.TEXT_MUTED,
                anchor="w",
                fg_color="transparent",
            ).grid(
                row=0,
                column=index,
                sticky="w",
                padx=(4, 4),
            )

        # =====================================================
        # Empty State
        # =====================================================

        self.empty_state = ctk.CTkFrame(
            self,
            fg_color=colors.SURFACE,
            border_width=1,
            border_color=colors.DIVIDER,
            corner_radius=8,
        )

        # Transparent container centered with padding
        # to provide natural height and spacing.
        content_box = ctk.CTkFrame(
            self.empty_state,
            fg_color="transparent",
        )

        content_box.pack(
            pady=24,
            padx=14,
        )

        # Blue accent line indicator
        ctk.CTkFrame(
            content_box,
            width=3,
            height=24,
            fg_color=colors.INFO,
            corner_radius=2,
        ).pack(
            pady=(0, 6),
        )

        # Empty-state icon
        self.empty_icon = ctk.CTkLabel(
            content_box,
            text="▣",
            font=(fonts.FONT_FAMILY, 20),
            text_color=colors.INFO,
        )

        self.empty_icon.pack(
            pady=(0, 6),
        )

        # Main empty-state text
        self.empty_title = ctk.CTkLabel(
            content_box,
            text="No products being monitored",
            font=fonts.SUBTITLE,
            text_color=colors.TEXT_PRIMARY,
        )

        self.empty_title.pack()

        # Empty-state description
        self.empty_description = ctk.CTkLabel(
            content_box,
            text=(
                "Add a Shopee product above to start monitoring "
                "its price and stock."
            ),
            font=fonts.SMALL,
            text_color=colors.TEXT_SECONDARY,
        )

        self.empty_description.pack(
            pady=(4, 0),
        )

        self.empty_state.pack(
            fill="x",
            padx=4,
            pady=3,
        )

    # =========================================================
    # Product Management
    # =========================================================

    def update_product(self, product):
        self.empty_state.pack_forget()

        if product.url in self.cards:
            self.cards[product.url].update_data(product)
            return

        card = ProductCard(
            self,
            product,
            stop_callback=self.stop_callback,
            set_target_callback=self.set_target_callback,
        )

        card.pack(
            fill="x",
            padx=4,
            pady=3,
        )

        self.cards[product.url] = card

    def remove_product(self, url):
        card = self.cards.pop(url, None)

        if card:
            card.destroy()

        if not self.cards:
            self.empty_state.pack(
                fill="x",
                padx=4,
                pady=3,
            )

    def clear(self):
        for card in self.cards.values():
            card.destroy()

        self.cards.clear()

        self.empty_state.pack(
            fill="x",
            padx=4,
            pady=3,
        )

    def count(self):
        return len(self.cards)