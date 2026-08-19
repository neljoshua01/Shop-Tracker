import customtkinter as ctk

from ui import colors, fonts


class AlertsPage(ctk.CTkFrame):

    def __init__(self, master):
        super().__init__(
            master,
            fg_color=colors.BACKGROUND
        )

        self.build_ui()

    def build_ui(self):

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # ==================================================
        # Page Header
        # ==================================================

        header = ctk.CTkFrame(
            self,
            fg_color="transparent"
        )

        header.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=20,
            pady=(20, 12)
        )

        ctk.CTkLabel(
            header,
            text="Alerts",
            font=fonts.TITLE,
            text_color=colors.TEXT_PRIMARY
        ).pack(
            anchor="w"
        )

        ctk.CTkLabel(
            header,
            text="View price, stock, and checkout alerts.",
            font=fonts.BODY,
            text_color=colors.TEXT_SECONDARY
        ).pack(
            anchor="w",
            pady=(4, 0)
        )

        # ==================================================
        # Alerts Container
        # ==================================================

        self.alerts_card = ctk.CTkFrame(
            self,
            fg_color=colors.CARD,
            border_width=1,
            border_color=colors.BORDER,
            corner_radius=8
        )

        self.alerts_card.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=20,
            pady=(0, 20)
        )

        self.alerts_card.grid_columnconfigure(
            0,
            weight=1
        )

        self.alerts_card.grid_rowconfigure(
            1,
            weight=1
        )

        # ==================================================
        # Alerts Header
        # ==================================================

        alerts_header = ctk.CTkFrame(
            self.alerts_card,
            fg_color="transparent"
        )

        alerts_header.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=16,
            pady=(16, 12)
        )

        alerts_header.grid_columnconfigure(
            0,
            weight=1
        )

        ctk.CTkLabel(
            alerts_header,
            text="Recent Alerts",
            font=fonts.HEADING,
            text_color=colors.TEXT_PRIMARY
        ).grid(
            row=0,
            column=0,
            sticky="w"
        )

        self.clear_button = ctk.CTkButton(
            alerts_header,
            text="Clear",
            width=80,
            height=32,
            fg_color="transparent",
            hover_color=colors.CARD_HOVER,
            border_width=1,
            border_color=colors.BORDER,
            text_color=colors.TEXT_SECONDARY,
            font=fonts.BUTTON,
            command=self.clear_alerts
        )

        self.clear_button.grid(
            row=0,
            column=1,
            sticky="e"
        )

        # ==================================================
        # Alert List
        # ==================================================

        self.alerts_list = ctk.CTkScrollableFrame(
            self.alerts_card,
            fg_color=colors.SURFACE_LIGHT,
            border_width=1,
            border_color=colors.BORDER,
            corner_radius=6
        )

        self.alerts_list.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=16,
            pady=(0, 16)
        )

        self.empty_label = ctk.CTkLabel(
            self.alerts_list,
            text="No alerts yet.",
            font=fonts.BODY,
            text_color=colors.TEXT_SECONDARY
        )

        self.empty_label.pack(
            pady=40
        )

    # ==================================================
    # Alert Controls
    # ==================================================

    def clear_alerts(self):

        for widget in self.alerts_list.winfo_children():
            widget.destroy()

        self.empty_label = ctk.CTkLabel(
            self.alerts_list,
            text="No alerts yet.",
            font=fonts.BODY,
            text_color=colors.TEXT_SECONDARY
        )

        self.empty_label.pack(
            pady=40
        )

    def append_alert(
        self,
        title,
        message,
        alert_type="info"
    ):

        if hasattr(self, "empty_label") and self.empty_label.winfo_exists():
            self.empty_label.destroy()

        if alert_type == "success":
            badge_bg = colors.SUCCESS_BG
            badge_color = colors.SUCCESS

        elif alert_type == "warning":
            badge_bg = colors.WARNING_BG
            badge_color = colors.WARNING

        elif alert_type == "danger":
            badge_bg = colors.DANGER_BG
            badge_color = colors.DANGER

        else:
            badge_bg = colors.CARD_HOVER
            badge_color = colors.TEXT_SECONDARY

        alert = ctk.CTkFrame(
            self.alerts_list,
            fg_color=colors.CARD,
            border_width=1,
            border_color=colors.BORDER,
            corner_radius=6
        )

        alert.pack(
            fill="x",
            padx=8,
            pady=6
        )

        alert.grid_columnconfigure(
            1,
            weight=1
        )

        badge = ctk.CTkLabel(
            alert,
            text=alert_type.upper(),
            width=70,
            height=24,
            corner_radius=12,
            font=fonts.SMALL_BOLD,
            fg_color=badge_bg,
            text_color=badge_color
        )

        badge.grid(
            row=0,
            column=0,
            rowspan=2,
            padx=(12, 10),
            pady=12
        )

        ctk.CTkLabel(
            alert,
            text=title,
            font=fonts.SUBTITLE,
            text_color=colors.TEXT_PRIMARY,
            anchor="w"
        ).grid(
            row=0,
            column=1,
            sticky="w",
            padx=(0, 12),
            pady=(10, 2)
        )

        ctk.CTkLabel(
            alert,
            text=message,
            font=fonts.SMALL,
            text_color=colors.TEXT_SECONDARY,
            anchor="w",
            justify="left",
            wraplength=700
        ).grid(
            row=1,
            column=1,
            sticky="ew",
            padx=(0, 12),
            pady=(0, 10)
        )