import customtkinter as ctk

from ui import colors, fonts


class DashboardHeader(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(
            master,
            fg_color="transparent",
            corner_radius=0
        )

        self.grid_columnconfigure(0, weight=1)
        self.build_ui()

    def build_ui(self):
        title_row = ctk.CTkFrame(self, fg_color="transparent")
        title_row.grid(row=0, column=0, sticky="ew")
        title_row.grid_columnconfigure(1, weight=1)

        ctk.CTkFrame(
            title_row,
            width=3,
            height=34,
            fg_color=colors.PRIMARY,
            corner_radius=2
        ).grid(row=0, column=0, sticky="ns", padx=(0, 10))

        ctk.CTkLabel(
            title_row,
            text="Dashboard",
            font=fonts.TITLE,
            text_color=colors.TEXT_PRIMARY
        ).grid(row=0, column=1, sticky="w")

        ctk.CTkLabel(
            self,
            text="Overview of your tracking and automation system",
            font=fonts.BODY,
            text_color=colors.TEXT_SECONDARY
        ).grid(row=1, column=0, sticky="w", padx=(13, 0), pady=(1, 0))
