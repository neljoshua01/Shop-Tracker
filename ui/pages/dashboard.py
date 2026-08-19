import customtkinter as ctk

from ui import colors, fonts

from ui.components.dashboard_header import DashboardHeader
from ui.components.dashboard_stats import DashboardStats
from ui.components.topbar import TopBar
from ui.components.status_bar import StatusBar
from ui.components.product_list import ProductList


class DashboardPage(ctk.CTkFrame):

    def __init__(
        self,
        master,
        start_monitoring_callback,
        stop_monitoring_callback,
        purchase_profile_callback=None,
    ):
        super().__init__(master, fg_color=colors.BACKGROUND)

        self.start_monitoring_callback = start_monitoring_callback
        self.stop_monitoring_callback = stop_monitoring_callback
        self.purchase_profile_callback = purchase_profile_callback

        self.build_ui()

    def build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=0)
        self.grid_rowconfigure(3, weight=0)
        self.grid_rowconfigure(4, weight=0)
        self.grid_rowconfigure(5, weight=1)
        self.grid_rowconfigure(6, weight=0)

        content_pad = 22

        self.dashboard_header = DashboardHeader(self)
        self.dashboard_header.grid(
            row=0, column=0, sticky="ew",
            padx=content_pad, pady=(18, 10)
        )

        self.topbar = TopBar(
            self,
            add_callback=self.start_monitoring_callback,
            purchase_profile_callback=self.purchase_profile_callback,
        )
        self.topbar.grid(
            row=1, column=0, sticky="ew",
            padx=content_pad, pady=(0, 10)
        )

        self.status_bar = StatusBar(self)
        self.status_bar.grid(
            row=2, column=0, sticky="ew",
            padx=content_pad, pady=(0, 10)
        )

        self.stats = DashboardStats(self)
        self.stats.grid(
            row=3, column=0, sticky="ew",
            padx=content_pad, pady=(0, 14)
        )

        products_heading = ctk.CTkFrame(self, fg_color="transparent")
        products_heading.grid(
            row=4, column=0, sticky="ew",
            padx=content_pad, pady=(0, 6)
        )
        products_heading.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            products_heading,
            text="Products Being Monitored",
            font=fonts.HEADING,
            text_color=colors.TEXT_PRIMARY
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            products_heading,
            text="LIVE WORKSPACE",
            font=fonts.SMALL_BOLD,
            text_color=colors.INFO
        ).grid(row=0, column=1, sticky="e")

        self.products_frame = ProductList(
            self,
            stop_callback=self.stop_monitoring_callback,
            fg_color=colors.SURFACE,
            border_width=1,
            border_color=colors.BORDER,
            corner_radius=10,
            height=280
        )
        self.products_frame.grid(
            row=5, column=0, sticky="nsew",
            padx=content_pad, pady=(0, 14)
        )

        bottom_frame = ctk.CTkFrame(self, fg_color="transparent", height=220)
        bottom_frame.grid(
            row=6, column=0, sticky="ew",
            padx=content_pad, pady=(0, 10)
        )
        bottom_frame.grid_propagate(False)
        bottom_frame.grid_columnconfigure(0, weight=1)
        bottom_frame.grid_rowconfigure(0, weight=1)

        self.build_system_response_log(bottom_frame)

    def build_system_response_log(self, parent):
        log_frame = ctk.CTkFrame(
            parent,
            fg_color=colors.CARD,
            border_width=1,
            border_color=colors.BORDER_STRONG,
            corner_radius=10
        )
        log_frame.grid(row=0, column=0, sticky="nsew")

        header = ctk.CTkFrame(log_frame, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(11, 7))

        title_frame = ctk.CTkFrame(header, fg_color="transparent")
        title_frame.pack(side="left")

        ctk.CTkLabel(
            title_frame,
            text="System Response Log",
            font=fonts.HEADING,
            text_color=colors.TEXT_PRIMARY
        ).pack(anchor="w")

        ctk.CTkLabel(
            title_frame,
            text="Live system and monitoring activity",
            font=fonts.SMALL,
            text_color=colors.TEXT_MUTED
        ).pack(anchor="w", pady=(1, 0))

        ctk.CTkLabel(
            header,
            text="●  LIVE CONSOLE",
            font=fonts.SMALL_BOLD,
            text_color=colors.SUCCESS
        ).pack(side="left", padx=(16, 0))

        ctk.CTkButton(
            header,
            text="Clear",
            width=68,
            height=28,
            fg_color=colors.PRIMARY_SOFT,
            hover_color=colors.CARD_HOVER,
            text_color=colors.PRIMARY_HOVER,
            font=fonts.SMALL_BOLD,
            border_width=1,
            border_color=colors.PRIMARY_GLOW,
            command=self.clear_logs
        ).pack(side="right")

        log_container = ctk.CTkFrame(
            log_frame,
            fg_color=colors.SURFACE,
            border_width=1,
            border_color=colors.DIVIDER,
            corner_radius=7
        )
        log_container.pack(fill="both", expand=True, padx=16, pady=(0, 11))

        self.log_box = ctk.CTkTextbox(
            log_container,
            height=100,
            font=fonts.LOG,
            fg_color="transparent",
            border_width=0,
            text_color=colors.TEXT_SECONDARY,
            scrollbar_button_color=colors.BORDER,
            scrollbar_button_hover_color=colors.CARD_HOVER
        )

        self.log_box.tag_config("log_success", foreground=colors.SUCCESS)
        self.log_box.tag_config("log_info", foreground=colors.INFO)
        self.log_box.tag_config("log_warning", foreground=colors.WARNING)
        self.log_box.tag_config("log_error", foreground=colors.DANGER)
        self.log_box.tag_config("log_time", foreground=colors.TEXT_MUTED)
        self.log_box.tag_config("log_message", foreground=colors.TEXT_PRIMARY)

        self.log_box.pack(fill="both", expand=True, padx=9, pady=7)

    def clear_logs(self):
        self.log_box.delete("1.0", "end")
