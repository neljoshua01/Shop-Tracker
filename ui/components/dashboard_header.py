import customtkinter as ctk

from ui import colors, fonts


class DashboardHeader(ctk.CTkFrame):

    def __init__(self, master):

        super().__init__(
            master,
            fg_color=colors.BACKGROUND,
            corner_radius=0
        )

        self.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(
            self,
            text="Dashboard",
            font=fonts.TITLE,
            text_color=colors.TEXT_PRIMARY
        )

        title.grid(row=0, column=0, sticky="w")

        subtitle = ctk.CTkLabel(
            self,
            text="Track prices and get notified on deals",
            font=fonts.BODY,
            text_color=colors.TEXT_SECONDARY
        )

        subtitle.grid(row=1, column=0, sticky="w", pady=(0, 5))
