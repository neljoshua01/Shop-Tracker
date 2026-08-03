import customtkinter as ctk

from ui import colors, fonts
from core.config.config_service import ConfigService


class Sidebar(ctk.CTkFrame):

    def __init__(self, master):

        super().__init__(
            master,
            width=220,
            fg_color=colors.SIDEBAR,
            corner_radius=0
        )

        self.pack_propagate(False)

        self.config_service = ConfigService()
        self.config = self.config_service.load()

        self.build_ui()

    def build_ui(self):

        brand_frame = ctk.CTkFrame(
            self,
            fg_color="transparent"
        )

        brand_frame.pack(
            fill="x",
            padx=18,
            pady=(24, 28)
        )

        logo = ctk.CTkLabel(
            brand_frame,
            text="S",
            width=34,
            height=34,
            fg_color=colors.DANGER,
            corner_radius=10,
            font=("Segoe UI", 18, "bold"),
            text_color=colors.TEXT_PRIMARY
        )

        logo.pack(side="left", padx=(0, 10))

        title = ctk.CTkLabel(
            brand_frame,
            text="Shopee\nPrice Tracker",
            font=("Segoe UI", 17, "bold"),
            justify="left",
            text_color=colors.TEXT_PRIMARY
        )

        title.pack(side="left", anchor="w")

        buttons = [
            ("⌂", "Dashboard", True),
            ("▣", "Products", False),
            ("◴", "Activity Logs", False),
            ("♢", "Alerts &\nAuto Checkout", False),
            ("ⓘ", "About", False)
        ]

        for icon, text, selected in buttons:

            button = ctk.CTkButton(
                self,
                text=f"{icon}   {text}",
                anchor="w",
                height=44,
                fg_color=colors.PRIMARY_SOFT if selected else "transparent",
                hover_color=colors.CARD_HOVER,
                text_color=colors.TEXT_PRIMARY,
                font=fonts.BUTTON,
                command=lambda: None
            )

            button.pack(
                fill="x",
                padx=15,
                pady=5
            )

        # =====================================================
        # Armed Mode Card
        # =====================================================

        self.armed_card = ctk.CTkFrame(
            self,
            fg_color=colors.CARD,
            border_width=1,
            border_color=colors.BORDER,
            corner_radius=8
        )

        self.armed_card.pack(
            side="bottom",
            fill="x",
            padx=15,
            pady=(0, 20)
        )

        ctk.CTkLabel(
            self.armed_card,
            text="⚡ ARMED MODE",
            font=("Segoe UI", 11, "bold"),
            text_color=colors.TEXT_PRIMARY
        ).pack(
            anchor="w",
            padx=14,
            pady=(14, 6)
        )

        self.armed_status = ctk.CTkLabel(
            self.armed_card,
            text="",
            font=fonts.BODY
        )

        self.armed_status.pack(
            anchor="w",
            padx=14,
            pady=(0, 10)
        )
        self.armed_var = ctk.BooleanVar(
            value=self.config["armed_mode"]
        )
        self.armed_switch = ctk.CTkSwitch(
            self.armed_card,
            text="Enable Live Purchases",
            variable=self.armed_var,
            command=self.toggle_armed_mode
        )

        self.armed_switch.pack(
            anchor="w",
            padx=14,
            pady=(0, 14)
        )
        
        if self.config["armed_mode"]:

            self.armed_status.configure(
                text="🔴 LIVE PURCHASE",
                text_color=colors.DANGER
            )

        else:

            self.armed_status.configure(
                text="🟢 SAFE MODE",
                text_color=colors.SUCCESS
            )

    def toggle_armed_mode(self):

        self.config["armed_mode"] = self.armed_var.get()

        self.config_service.save(
            self.config
        )

        if self.config["armed_mode"]:

            self.armed_status.configure(
                text="🔴 LIVE PURCHASE",
                text_color=colors.DANGER
            )

            print("[Sidebar] Armed Mode ENABLED")

        else:

            self.armed_status.configure(
                text="🟢 SAFE MODE",
                text_color=colors.SUCCESS
            )

            print("[Sidebar] Armed Mode DISABLED")