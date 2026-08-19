import customtkinter as ctk

from core.config.config_service import ConfigService
from ui import colors, fonts, icons


class Sidebar(ctk.CTkFrame):

    def __init__(self, master, nav_callback=None):

        super().__init__(
            master,
            width=232,
            fg_color=colors.SIDEBAR,
            corner_radius=0
        )

        self.pack_propagate(False)
        self.nav_callback = nav_callback
        self.nav_buttons = {}

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
            pady=(22, 28)
        )

        logo = ctk.CTkFrame(
            brand_frame,
            width=38,
            height=38,
            fg_color="transparent",
            border_width=1,
            border_color=colors.PRIMARY,
            corner_radius=11
        )
        logo.pack_propagate(False)
        logo.pack(side="left", padx=(0, 11))

        ctk.CTkLabel(
            logo,
            text="S",
            font=fonts.HEADING,
            text_color=colors.PRIMARY_HOVER
        ).pack(expand=True)

        title = ctk.CTkLabel(
            brand_frame,
            text="Shopee\nPrice Tracker",
            font=fonts.BRAND,
            justify="left",
            text_color=colors.TEXT_PRIMARY
        )

        title.pack(side="left", anchor="w")

        buttons = [
            (icons.DASHBOARD, "Dashboard", True),
            (icons.PRODUCTS, "Products", False),
            (icons.LOGS, "Activity Logs", False),
            (icons.ALERT, "Alerts &\nAuto Checkout", False),
            (icons.SETTINGS, "Settings", False),
        ]

        for icon_path, text, selected in buttons:

            icon_color = colors.PRIMARY_HOVER if selected else colors.TEXT_MUTED
            icon_image = icons.load_icon(
                icon_path,
                icon_color,
                icons.SIZE_DEFAULT,
            )

            button = ctk.CTkButton(
                self,
                text=text,
                image=icon_image,
                compound="left",
                anchor="w",
                height=44,
                fg_color=(
                    colors.PRIMARY_SOFT
                    if selected
                    else "transparent"
                ),
                hover_color=colors.CARD_HOVER,
                text_color=(
                    colors.TEXT_PRIMARY
                    if selected
                    else colors.TEXT_SECONDARY
                ),
                font=fonts.BUTTON,
                border_width=1 if selected else 0,
                border_color=colors.PRIMARY_GLOW if selected else "transparent",
                command=lambda page=text: self.navigate(page),
            )

            button.pack(
                fill="x",
                padx=14,
                pady=4
            )

            self.nav_buttons[text] = button

        # =====================================================
        # Armed Mode Card
        # =====================================================

        self.armed_card = ctk.CTkFrame(
            self,
            fg_color=colors.CARD,
            border_width=1,
            border_color=colors.BORDER_STRONG,
            corner_radius=10
        )

        self.armed_card.pack(
            side="bottom",
            fill="x",
            padx=14,
            pady=(0, 18)
        )

        ctk.CTkLabel(
            self.armed_card,
            text="⚡  ARMED MODE",
            font=fonts.BADGE,
            text_color=colors.TEXT_PRIMARY
        ).pack(
            anchor="w",
            padx=14,
            pady=(13, 5)
        )

        self.armed_status = ctk.CTkLabel(
            self.armed_card,
            text="",
            font=fonts.BODY
        )

        self.armed_status.pack(
            anchor="w",
            padx=14,
            pady=(0, 9)
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
            pady=(0, 13)
        )

        self._update_armed_status()

    def navigate(self, page):

        if self.nav_callback:
            self.nav_callback(page)

    def _update_armed_status(self):

        if self.config["armed_mode"]:

            self.armed_status.configure(
                text="●  LIVE PURCHASE",
                text_color=colors.DANGER
            )

        else:

            self.armed_status.configure(
                text="●  SAFE MODE",
                text_color=colors.SUCCESS
            )

    def toggle_armed_mode(self):

        self.config["armed_mode"] = self.armed_var.get()

        self.config_service.save(
            self.config
        )

        self._update_armed_status()

        if self.config["armed_mode"]:
            print("[Sidebar] Armed Mode ENABLED")
        else:
            print("[Sidebar] Armed Mode DISABLED")
