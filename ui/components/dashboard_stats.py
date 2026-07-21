import customtkinter as ctk

from ui import colors, fonts
from ui import icons


class StatCard(ctk.CTkFrame):

    def __init__(
        self,
        master,
        title,
        value,
        subtitle="",
        image=None
    ):
        super().__init__(
            master,
            fg_color=colors.CARD,
            corner_radius=8,
            border_width=1,
            border_color=colors.BORDER
        )

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.image = image

        self.icon = ctk.CTkLabel(
            self,
            text="",
            image=self.image,
        )

        self.icon.grid(
            row=0,
            column=0,
            rowspan=3,
            padx=18,
            pady=18,
            sticky="n"
        )

        self.title = ctk.CTkLabel(
            self,
            text=title,
            font=fonts.BODY,
            text_color=colors.TEXT_PRIMARY
        )

        self.title.grid(
            row=0,
            column=1,
            sticky="sw",
            padx=(0, 20),
            pady=(18, 0)
        )

        self.value = ctk.CTkLabel(
            self,
            text=value,
            font=("Segoe UI", 22, "bold"),
            text_color=colors.TEXT_PRIMARY
        )

        self.value.grid(
            row=1,
            column=1,
            sticky="nw",
            padx=(0, 20)
        )

        self.subtitle = ctk.CTkLabel(
            self,
            text=subtitle,
            font=fonts.SMALL,
            text_color=colors.TEXT_SECONDARY
        )

        self.subtitle.grid(
            row=2,
            column=1,
            sticky="nw",
            padx=(0, 20),
            pady=(0, 18)
        )

    def update(self, value):
        self.value.configure(text=value)


class DashboardStats(ctk.CTkFrame):

    def __init__(self, master):
        super().__init__(
            master,
            fg_color="transparent"
        )

        self.build_ui()

    def build_ui(self):
        self.products = StatCard(
            self,
            title="Products",
            value="0",
            subtitle="Being monitored",
            image=icons.PRODUCT
        )

        self.Purchased = StatCard(
            self,
            title="Products purchased",
            value="0",
            subtitle="With active discounts",
            image=icons.CART
        )

        self.lowest = StatCard(
            self,
            title="Lowest Price",
            value="--",
            subtitle="Best deal",
            image=icons.DISCOUNT
        )

        self.Response_time = StatCard(
            self,
            title="Ave. Response Time",
            value="--",
            subtitle="Today",
            image=icons.TIME
        )

        cards = [
            self.products,
            self.Purchased,
            self.lowest,
            self.Response_time
        ]

        for index, card in enumerate(cards):
            card.configure(height=96)
            card.grid(
                row=0,
                column=index,
                padx=(0, 14) if index < len(cards) - 1 else 0,
                sticky="nsew"
            )

        for index in range(4):
            self.grid_columnconfigure(index, weight=1)
