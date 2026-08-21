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
        image=None,
        accent=colors.PRIMARY,
        accent_bg=colors.PRIMARY_SOFT,
    ):
        super().__init__(
            master,
            fg_color=colors.CARD,
            corner_radius=9,
            border_width=1,
            border_color=colors.BORDER,
            height=84,
        )
        self.grid_propagate(False)

        # ---------------------------------------------------------
        # Icon
        # ---------------------------------------------------------
        icon_shell = ctk.CTkFrame(
            self,
            width=48,
            height=48,
            fg_color=accent_bg,
            border_width=1,
            border_color=accent,
            corner_radius=24,
        )
        icon_shell.place(
            x=11,
            rely=0.5,
            anchor="w",
        )
        icon_shell.grid_propagate(False)

        icon_image = icons.load_icon(
            image,
            accent,
            icons.SIZE_DEFAULT,
        )

        ctk.CTkLabel(
            icon_shell,
            text="",
            image=icon_image,
        ).place(
            relx=0.5,
            rely=0.5,
            anchor="center",
        )

        # ---------------------------------------------------------
        # Vertically centered text block
        # ---------------------------------------------------------
        text_container = ctk.CTkFrame(
            self,
            fg_color="transparent",
        )
        text_container.place(
            x=69,
            rely=0.5,
            anchor="w",
        )

        # Title
        ctk.CTkLabel(
            text_container,
            text=title,
            font=fonts.SMALL,
            text_color=colors.TEXT_SECONDARY,
            anchor="w",
            height=17,
        ).pack(
            anchor="w",
        )

        # Main value
        self.value = ctk.CTkLabel(
            text_container,
            text=value,
            font=fonts.STAT_VALUE,
            text_color=colors.TEXT_PRIMARY,
            anchor="w",
            height=25,
        )
        self.value.pack(
            anchor="w",
            pady=(1, 0),
        )

        # Secondary text
        ctk.CTkLabel(
            text_container,
            text=subtitle,
            font=fonts.SMALL,
            text_color=colors.TEXT_MUTED,
            anchor="w",
            height=17,
        ).pack(
            anchor="w",
            pady=(1, 0),
        )
    def update(self, value):
        self.value.configure(text=value)


class DashboardStats(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self.build_ui()

    def build_ui(self):
        self.products = StatCard(self, "Products", "0", "Being monitored", icons.PRODUCT, colors.PRIMARY, colors.PRIMARY_SOFT)
        self.Purchased = StatCard(self, "Products purchased", "0", "With active discounts", icons.CART, colors.SUCCESS, colors.SUCCESS_BG)
        self.lowest = StatCard(self, "Lowest Price", "--", "Best deal", icons.DISCOUNT, colors.WARNING, colors.WARNING_BG)
        self.Response_time = StatCard(self, "Ave. Response Time", "--", "Today", icons.TIME, colors.INFO, colors.INFO_BG)
        cards = [self.products, self.Purchased, self.lowest, self.Response_time]
        for index, card in enumerate(cards):
            self.grid_columnconfigure(index, weight=1, uniform="stat")
            card.grid(row=0, column=index, sticky="ew", padx=(0, 9) if index < 3 else 0)
