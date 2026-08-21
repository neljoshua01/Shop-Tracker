import customtkinter as ctk

from datetime import datetime
from ui import colors, fonts


class StatusBar(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(
            master,
            fg_color=colors.SURFACE,
            border_width=1,
            border_color=colors.BORDER,
            corner_radius=9,
            height=46,
        )
        self.pack_propagate(False)
        self.engine_state = "IDLE"
        self.build_ui()

    def build_ui(self):
        self.activity_rail = ctk.CTkFrame(
            self,
            width=4,
            height=26,
            fg_color=colors.INFO,
            corner_radius=2,
        )
        self.activity_rail.pack(side="left", padx=(9, 8), pady=10)

        self.live_label = ctk.CTkLabel(
            self,
            text="●  IDLE",
            width=70,
            height=26,
            font=fonts.STATUS,
            text_color=colors.INFO,
            fg_color=colors.INFO_BG,
            corner_radius=8,
        )
        self.live_label.pack(side="left", padx=(0, 10))

        self.status_label = ctk.CTkLabel(
            self,
            text="Monitoring 0 Products",
            font=fonts.BODY,
            text_color=colors.TEXT_PRIMARY,
        )
        self.status_label.pack(side="left")

        self.last_update = ctk.CTkLabel(
            self,
            text="Last updated: --",
            font=fonts.SMALL,
            text_color=colors.TEXT_SECONDARY,
        )
        self.last_update.pack(side="right", padx=(0, 10))

        self.refresh_icon = ctk.CTkButton(
            self,
            text="↻",
            width=28,
            height=28,
            fg_color="transparent",
            hover_color=colors.CARD_HOVER,
            text_color=colors.TEXT_SECONDARY,
            border_width=1,
            border_color=colors.BORDER,
            font=fonts.BODY,
            command=lambda: None,
        )
        self.refresh_icon.pack(side="right", padx=(0, 7))

    def update_engine_state(self, state):
        self.engine_state = state
        styles = {
            "IDLE": (colors.INFO, colors.INFO_BG),
            "STARTING": (colors.WARNING, colors.WARNING_BG),
            "RUNNING": (colors.SUCCESS, colors.SUCCESS_BG),
            "STOPPING": (colors.WARNING, colors.WARNING_BG),
            "ERROR": (colors.DANGER, colors.DANGER_BG),
        }
        text_color, background = styles.get(
            state,
            (colors.INFO, colors.INFO_BG),
        )
        self.activity_rail.configure(fg_color=text_color)
        self.live_label.configure(
            text=f"●  {state}",
            text_color=text_color,
            fg_color=background,
        )

    def update_product_count(self, count):
        self.status_label.configure(
            text=f"Monitoring {count} Product{'s' if count != 1 else ''}"
        )

    def update_timestamp(self):
        now = datetime.now().strftime("%I:%M:%S %p")
        self.last_update.configure(text=f"Last updated: {now}")
