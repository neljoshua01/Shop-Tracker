import customtkinter as ctk

from datetime import datetime
from ui import colors, fonts


class StatusBar(ctk.CTkFrame):

    def __init__(self, master):
        super().__init__(
            master,
            fg_color=colors.SURFACE,
            corner_radius=12,
            height=50
        )

        self.pack_propagate(False)

        self.build_ui()

    def build_ui(self):
        self.live_label = ctk.CTkLabel(
            self,
            text="●  IDLE",
            width=72,
            height=28,
            font=("Segoe UI", 12, "bold"),
            text_color=colors.DANGER,
            fg_color=colors.DANGER_BG,
            corner_radius=8
        )

        self.live_label.pack(
            side="left",
            padx=(18, 12)
        )

        self.status_label = ctk.CTkLabel(
            self,
            text="Monitoring 0 Products",
            font=fonts.BODY,
            text_color=colors.TEXT_PRIMARY
        )

        self.status_label.pack(
            side="left"
        )

        self.last_update = ctk.CTkLabel(
            self,
            text="Last updated: --",
            font=fonts.BODY,
            text_color=colors.TEXT_SECONDARY
        )

        self.last_update.pack(
            side="right",
            padx=(0, 20)
        )

        self.refresh_icon = ctk.CTkButton(
            self,
            text="↻",
            width=30,
            height=30,
            fg_color="transparent",
            hover_color=colors.CARD_HOVER,
            text_color=colors.TEXT_SECONDARY,
            command=lambda: None
        )

        self.refresh_icon.pack(
            side="right",
            padx=(0, 8)
        )

    def update_product_count(self, count):
        if count > 0:
            self.live_label.configure(
                text="●  LIVE",
                text_color=colors.SUCCESS,
                fg_color=colors.SUCCESS_BG
            )
        else:
            self.live_label.configure(
                text="●  IDLE",
                text_color=colors.DANGER,
                fg_color=colors.DANGER_BG
            )

        self.status_label.configure(
            text=f"Monitoring {count} Product{'s' if count != 1 else ''}"
        )

    def update_timestamp(self):
        now = datetime.now().strftime("%I:%M:%S %p")

        self.last_update.configure(
            text=f"Last updated: {now}"
        )
