import customtkinter as ctk

from core.config.config_service import ConfigService
from ui import colors, fonts, icons


class Sidebar(ctk.CTkFrame):
    def __init__(self, master, nav_callback=None):
        super().__init__(master, width=232, fg_color=colors.SIDEBAR, corner_radius=0)
        self.pack_propagate(False)
        self.nav_callback = nav_callback
        self.nav_buttons = {}
        self.nav_icon_paths = {}
        self.selected_page = "Dashboard"
        self.config_service = ConfigService()
        self.config = self.config_service.load()
        self.build_ui()

    def build_ui(self):
        brand_frame = ctk.CTkFrame(self, fg_color="transparent")
        brand_frame.pack(fill="x", padx=18, pady=(20, 24))

        logo = ctk.CTkFrame(
            brand_frame,
            width=36,
            height=36,
            fg_color="transparent",
            border_width=1,
            border_color=colors.PRIMARY,
            corner_radius=10,
        )
        logo.pack_propagate(False)
        logo.pack(side="left", padx=(0, 10))
        ctk.CTkLabel(logo, text="S", font=fonts.HEADING, text_color=colors.PRIMARY_HOVER).pack(expand=True)

        ctk.CTkLabel(
            brand_frame,
            text="Shopee\nPrice Tracker",
            font=fonts.BRAND,
            justify="left",
            text_color=colors.TEXT_PRIMARY,
        ).pack(side="left", anchor="w")

        buttons = [
            (icons.DASHBOARD, "Dashboard"),
            (icons.PRODUCTS, "Products"),
            (icons.LOGS, "Activity Logs"),
            (icons.ALERT, "Alerts &\nAuto Checkout"),
            (icons.SETTINGS, "Settings"),
        ]
        for icon_path, text in buttons:
            self.nav_icon_paths[text] = icon_path
            button = ctk.CTkButton(
                self,
                text=text,
                compound="left",
                anchor="w",
                height=42,
                hover_color=colors.CARD_HOVER,
                font=fonts.BUTTON,
                command=lambda page=text: self.navigate(page),
            )
            button.pack(fill="x", padx=14, pady=3)
            self.nav_buttons[text] = button
        self._update_selected_navigation()

        # Keep Armed Mode available as a compact safety control rather than a
        # large legacy card competing with the Dashboard workspace.
        self.armed_control = ctk.CTkFrame(
            self,
            fg_color="transparent",
            height=38,
        )
        self.armed_control.pack(side="bottom", fill="x", padx=14, pady=(0, 12))
        self.armed_control.pack_propagate(False)

        self.armed_var = ctk.BooleanVar(value=self.config["armed_mode"])
        self.armed_switch = ctk.CTkSwitch(
            self.armed_control,
            text="Armed Mode",
            variable=self.armed_var,
            command=self.toggle_armed_mode,
            font=fonts.SMALL_BOLD,
            text_color=colors.TEXT_SECONDARY,
            width=30,
        )
        self.armed_switch.pack(side="left", anchor="center")

        self.armed_status = ctk.CTkLabel(
            self.armed_control,
            text="",
            font=fonts.BADGE,
        )
        self.armed_status.pack(side="right", anchor="center", padx=(6, 0))
        self._update_armed_status()

    def navigate(self, page):
        self.selected_page = page
        self._update_selected_navigation()
        if self.nav_callback:
            self.nav_callback(page)

    def _update_selected_navigation(self):
        for page, button in self.nav_buttons.items():
            selected = page == self.selected_page
            icon_color = colors.PRIMARY_HOVER if selected else colors.TEXT_MUTED
            icon_image = icons.load_icon(self.nav_icon_paths[page], icon_color, icons.SIZE_DEFAULT)
            button.configure(
                image=icon_image,
                fg_color=colors.PRIMARY_SOFT if selected else "transparent",
                text_color=colors.TEXT_PRIMARY if selected else colors.TEXT_SECONDARY,
                border_width=1 if selected else 0,
                border_color=colors.PRIMARY_GLOW if selected else colors.SIDEBAR,
            )

    def _update_armed_status(self):
        if self.config["armed_mode"]:
            self.armed_status.configure(text="LIVE", text_color=colors.DANGER)
            self.armed_switch.configure(text_color=colors.TEXT_PRIMARY)
        else:
            self.armed_status.configure(text="SAFE", text_color=colors.SUCCESS)
            self.armed_switch.configure(text_color=colors.TEXT_SECONDARY)

    def toggle_armed_mode(self):
        self.config["armed_mode"] = self.armed_var.get()
        self.config_service.save(self.config)
        self._update_armed_status()
        if self.config["armed_mode"]:
            print("[Sidebar] Armed Mode ENABLED")
        else:
            print("[Sidebar] Armed Mode DISABLED")
