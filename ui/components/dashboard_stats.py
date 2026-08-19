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
            height=88,
        )
        self.grid_propagate(False)
        self.grid_columnconfigure(1, weight=1)
        icon_shell = ctk.CTkFrame(self, width=48, height=48, fg_color=accent_bg, border_width=1, border_color=accent, corner_radius=24)
        icon_shell.grid(row=0, column=0, rowspan=3, padx=(11, 10), pady=19)
        icon_shell.grid_propagate(False)
        icon_image = icons.load_icon(image, accent, icons.SIZE_DEFAULT)
        ctk.CTkLabel(icon_shell, text="", image=icon_image).place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(self, text=title, font=fonts.SMALL, text_color=colors.TEXT_SECONDARY).grid(row=0, column=1, sticky="sw", padx=(0, 10), pady=(10, 0))
        self.value = ctk.CTkLabel(self, text=value, font=fonts.STAT_VALUE, text_color=colors.TEXT_PRIMARY)
        self.value.grid(row=1, column=1, sticky="nw", padx=(0, 10))
        ctk.CTkLabel(self, text=subtitle, font=fonts.SMALL, text_color=colors.TEXT_MUTED).grid(row=2, column=1, sticky="nw", padx=(0, 10), pady=(0, 9))

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
