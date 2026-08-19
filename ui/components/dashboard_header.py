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

        accent = ctk.CTkFrame(
            self,
            width=4,
            height=46,
            fg_color=colors.PRIMARY,
            corner_radius=2
        )
        accent.grid(row=0, column=0, rowspan=2, sticky="nsw", pady=2)

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.grid(row=0, column=0, rowspan=2, sticky="ew", padx=(14, 0))

        title = ctk.CTkLabel(
            content,
            text="Dashboard",
            font=fonts.TITLE,
            text_color=colors.TEXT_PRIMARY
        )
        title.pack(anchor="w")

        subtitle = ctk.CTkLabel(
            content,
            text="Track prices and get notified on deals",
            font=fonts.BODY,
            text_color=colors.TEXT_SECONDARY
        )
        subtitle.pack(anchor="w", pady=(2, 0))
