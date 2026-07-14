import customtkinter as ctk

from ui import colors, fonts


class Sidebar(ctk.CTkFrame):

    def __init__(self, master):

        super().__init__(
            master,
            width=220,
            fg_color=colors.SIDEBAR,
            corner_radius=0
        )

        self.pack_propagate(False)

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
            ("⚙", "Settings", False),
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

        self.monitor_card = ctk.CTkFrame(
            self,
            fg_color=colors.CARD,
            border_width=1,
            border_color=colors.BORDER,
            corner_radius=8
        )

        self.monitor_card.pack(
            side="bottom",
            fill="x",
            padx=15,
            pady=(0, 20)
        )

        ctk.CTkLabel(
            self.monitor_card,
            text="● MONITORING",
            font=("Segoe UI", 11, "bold"),
            text_color=colors.SUCCESS
        ).pack(anchor="w", padx=14, pady=(14, 8))

        ctk.CTkLabel(
            self.monitor_card,
            text="0 Products",
            font=fonts.BODY,
            text_color=colors.TEXT_PRIMARY
        ).pack(anchor="w", padx=14)

        ctk.CTkLabel(
            self.monitor_card,
            text="Since app start",
            font=fonts.SMALL,
            text_color=colors.TEXT_SECONDARY
        ).pack(anchor="w", padx=14, pady=(2, 14))
