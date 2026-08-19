import customtkinter as ctk

from ui import colors, fonts, icons

from ui.components.dashboard_header import DashboardHeader
from ui.components.dashboard_stats import DashboardStats
from ui.components.topbar import TopBar
from ui.components.status_bar import StatusBar
from ui.components.product_list import ProductList


class DashboardPage(ctk.CTkFrame):
    """Dashboard presentation layer; live data still comes from MainWindow/controller."""

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
        self.grid_rowconfigure(4, weight=1)
        self.grid_rowconfigure(5, weight=0)

        content_pad = 18

        header_row = ctk.CTkFrame(self, fg_color="transparent")
        header_row.grid(row=0, column=0, sticky="ew", padx=content_pad, pady=(14, 7))
        header_row.grid_columnconfigure(0, weight=1)

        self.dashboard_header = DashboardHeader(header_row)
        self.dashboard_header.grid(row=0, column=0, sticky="w")
        self.build_engine_status(header_row)

        # Keep the existing purchase-profile action, but make the control
        # row visually secondary to the dashboard header and metrics.
        self.topbar = TopBar(
            self,
            add_callback=self.start_monitoring_callback,
            purchase_profile_callback=self.purchase_profile_callback,
        )
        self.topbar.grid(row=1, column=0, sticky="ew", padx=content_pad, pady=(0, 7))

        self.status_bar = StatusBar(self)
        self.status_bar.grid(row=2, column=0, sticky="ew", padx=content_pad, pady=(0, 9))

        self.stats = DashboardStats(self)
        self.stats.grid(row=3, column=0, sticky="ew", padx=content_pad, pady=(0, 11))

        workspace = ctk.CTkFrame(self, fg_color="transparent")
        workspace.grid(row=4, column=0, sticky="nsew", padx=content_pad, pady=(0, 10))
        workspace.grid_columnconfigure(0, weight=3, uniform="workspace")
        workspace.grid_columnconfigure(1, weight=1, uniform="workspace")
        workspace.grid_rowconfigure(0, weight=0)
        workspace.grid_rowconfigure(1, weight=1)

        self.build_engine_panel(workspace)
        self.build_products_panel(workspace)
        self.build_pipeline_panel(workspace)

        bottom = ctk.CTkFrame(self, fg_color="transparent", height=172)
        bottom.grid(row=5, column=0, sticky="ew", padx=content_pad, pady=(0, 9))
        bottom.grid_propagate(False)
        bottom.grid_columnconfigure(0, weight=1, uniform="console")
        bottom.grid_columnconfigure(1, weight=1, uniform="console")
        bottom.grid_columnconfigure(2, weight=2, uniform="console")
        bottom.grid_rowconfigure(0, weight=1)

        self.build_alerts_panel(bottom)
        self.build_engine_logs_panel(bottom)
        self.build_system_response_log(bottom)

    def build_engine_status(self, parent):
        engine_status = ctk.CTkFrame(
            parent,
            fg_color=colors.TOPBAR,
            border_width=1,
            border_color=colors.BORDER,
            corner_radius=9,
            width=214,
            height=52,
        )
        engine_status.grid(row=0, column=1, sticky="e", padx=(18, 0))
        engine_status.grid_propagate(False)

        ctk.CTkFrame(
            engine_status,
            width=10,
            height=10,
            fg_color=colors.SUCCESS,
            corner_radius=5,
        ).place(x=14, y=20)

        ctk.CTkLabel(
            engine_status,
            text="Engine Status",
            font=fonts.SMALL_BOLD,
            text_color=colors.TEXT_PRIMARY,
        ).place(x=34, y=8)

        ctk.CTkLabel(
            engine_status,
            text="All Systems Operational",
            font=fonts.SMALL,
            text_color=colors.TEXT_SECONDARY,
        ).place(x=34, y=27)

    def panel(self, parent, row, column, title, subtitle=None, action_text=None, action_command=None):
        frame = ctk.CTkFrame(
            parent,
            fg_color=colors.CARD,
            border_width=1,
            border_color=colors.BORDER,
            corner_radius=9,
        )
        frame.grid(
            row=row,
            column=column,
            sticky="nsew",
            padx=(0, 9) if column == 0 else 0,
            pady=0,
        )

        header = ctk.CTkFrame(frame, fg_color="transparent", height=38)
        header.pack(fill="x", padx=14, pady=(7, 0))
        header.pack_propagate(False)

        ctk.CTkLabel(
            header,
            text=title,
            font=fonts.HEADING,
            text_color=colors.TEXT_PRIMARY,
        ).pack(side="left", anchor="center")

        if action_text and action_command:
            ctk.CTkButton(
                header,
                text=action_text,
                command=action_command,
                width=126,
                height=28,
                corner_radius=6,
                fg_color=colors.PRIMARY,
                hover_color=colors.PRIMARY_HOVER,
                border_width=1,
                border_color=colors.PRIMARY_HOVER,
                font=fonts.SMALL_BOLD,
                text_color=colors.TEXT_PRIMARY,
            ).pack(side="right", anchor="center")
        elif subtitle:
            ctk.CTkLabel(
                header,
                text=subtitle,
                font=fonts.SMALL_BOLD,
                text_color=colors.INFO if "LIVE" in subtitle else colors.TEXT_MUTED,
            ).pack(side="right", anchor="center")

        return frame

    def build_engine_panel(self, parent):
        frame = self.panel(parent, 0, 0, "Monitoring Engine", "●  RUNNING")
        ctk.CTkLabel(
            frame,
            text="Analyzing  •  Detecting  •  Deciding  •  Triggering",
            font=fonts.SMALL,
            text_color=colors.TEXT_SECONDARY,
        ).pack(anchor="w", padx=14, pady=(0, 7))

        modules = ctk.CTkFrame(frame, fg_color="transparent")
        modules.pack(fill="x", padx=14, pady=(0, 10))
        for index in range(3):
            modules.grid_columnconfigure(index, weight=1, uniform="engine")

        stages = [
            ("Product State", "Tracks product & stock state", icons.STATE_MANAGER, colors.PRIMARY),
            ("Live Updates", "Receives monitoring updates", icons.TIME, colors.INFO),
            ("API Polling", "Refreshes monitored products", icons.API_POLLER, colors.PRIMARY_HOVER),
        ]
        for index, (title, text, icon, accent) in enumerate(stages):
            card = ctk.CTkFrame(
                modules,
                fg_color=colors.SURFACE,
                border_width=1,
                border_color=colors.DIVIDER,
                corner_radius=7,
                height=58,
            )
            card.grid(row=0, column=index, sticky="ew", padx=(0, 7) if index < 2 else 0)
            card.grid_propagate(False)

            icon_box = ctk.CTkFrame(
                card,
                width=36,
                height=36,
                fg_color=colors.PRIMARY_SOFT if accent != colors.INFO else colors.INFO_BG,
                border_width=1,
                border_color=accent,
                corner_radius=7,
            )
            icon_box.place(x=8, y=10)
            icon_image = icons.load_icon(icon, accent, icons.SIZE_SMALL)
            ctk.CTkLabel(icon_box, text="", image=icon_image).place(relx=0.5, rely=0.5, anchor="center")
            ctk.CTkLabel(card, text=title, font=fonts.SMALL_BOLD, text_color=colors.TEXT_PRIMARY).place(x=53, y=8)
            ctk.CTkLabel(card, text=text, font=fonts.SMALL, text_color=colors.TEXT_MUTED).place(x=53, y=29)

    def build_products_panel(self, parent):
        frame = self.panel(
            parent,
            1,
            0,
            "Active Products",
            action_text="Add Purchase Profile",
            action_command=self.purchase_profile_callback,
        )
        frame.grid_configure(pady=(9, 0))
        self.products_frame = ProductList(
            frame,
            stop_callback=self.stop_monitoring_callback,
            fg_color=colors.SURFACE,
            border_width=1,
            border_color=colors.BORDER,
            corner_radius=8,
            height=190,
        )
        self.products_frame.pack(fill="both", expand=True, padx=9, pady=(0, 9))

    def build_pipeline_panel(self, parent):
        frame = self.panel(parent, 0, 1, "System Pipeline", "LIVE")
        frame.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=0)
        pipeline = ctk.CTkFrame(frame, fg_color="transparent")
        pipeline.pack(fill="both", expand=True, padx=10, pady=(0, 9))

        stages = [
            ("Shopee Product", "Input source", colors.INFO),
            ("Monitoring Controller", "Tracking state", colors.PRIMARY_HOVER),
            ("Purchase Profile", "Purchase configuration", colors.PRIMARY),
            ("Monitoring / Purchase", "Existing application flow", colors.SUCCESS),
            ("System Response Log", "Live UI feedback", colors.INFO),
        ]
        for index, (name, detail, accent) in enumerate(stages):
            row = ctk.CTkFrame(
                pipeline,
                fg_color=colors.SURFACE,
                border_width=1,
                border_color=colors.DIVIDER,
                corner_radius=7,
                height=42,
            )
            row.pack(fill="x", pady=(0, 3))
            row.pack_propagate(False)
            ctk.CTkFrame(row, width=3, height=24, fg_color=accent, corner_radius=2).place(x=9, y=8)
            ctk.CTkLabel(row, text=name, font=fonts.SMALL_BOLD, text_color=colors.TEXT_PRIMARY).place(x=20, y=6)
            ctk.CTkLabel(row, text=detail, font=fonts.SMALL, text_color=colors.TEXT_MUTED).place(x=20, y=23)
            if index < len(stages) - 1:
                ctk.CTkLabel(
                    pipeline,
                    text="↓",
                    font=(fonts.FONT_FAMILY, 10),
                    text_color=colors.TEXT_MUTED,
                ).pack(pady=(0, 1))

    def build_alerts_panel(self, parent):
        frame = self.panel(parent, 0, 0, "Recent Alerts", "VIEW ALL")
        frame.grid_configure(padx=(0, 6))
        empty = ctk.CTkFrame(frame, fg_color="transparent")
        empty.pack(fill="both", expand=True, padx=12, pady=(0, 9))
        ctk.CTkLabel(
            empty,
            text="No active alerts",
            font=fonts.SUBTITLE,
            text_color=colors.TEXT_PRIMARY,
        ).pack(pady=(14, 3))
        ctk.CTkLabel(
            empty,
            text="Price and stock alerts will appear here.",
            font=fonts.SMALL,
            text_color=colors.TEXT_MUTED,
        ).pack()

    def build_engine_logs_panel(self, parent):
        frame = self.panel(parent, 0, 1, "Engine Logs", "VIEW ALL")
        frame.grid_configure(padx=(6, 6))
        log_area = ctk.CTkFrame(
            frame,
            fg_color=colors.SURFACE,
            border_width=1,
            border_color=colors.DIVIDER,
            corner_radius=7,
        )
        log_area.pack(fill="both", expand=True, padx=9, pady=(0, 9))
        ctk.CTkLabel(
            log_area,
            text="Engine events are surfaced through the\nSystem Response Log below.",
            font=fonts.SMALL,
            text_color=colors.TEXT_MUTED,
            justify="center",
        ).pack(expand=True)

    def build_system_response_log(self, parent):
        log_frame = self.panel(parent, 0, 2, "System Response Log", "LIVE CONSOLE")
        log_frame.grid_configure(padx=(6, 0))
        log_container = ctk.CTkFrame(
            log_frame,
            fg_color=colors.SURFACE,
            border_width=1,
            border_color=colors.DIVIDER,
            corner_radius=7,
        )
        log_container.pack(fill="both", expand=True, padx=9, pady=(0, 9))
        self.log_box = ctk.CTkTextbox(
            log_container,
            height=100,
            font=fonts.LOG,
            fg_color="transparent",
            border_width=0,
            text_color=colors.TEXT_SECONDARY,
            scrollbar_button_color=colors.BORDER,
            scrollbar_button_hover_color=colors.CARD_HOVER,
        )
        self.log_box.tag_config("log_success", foreground=colors.SUCCESS)
        self.log_box.tag_config("log_info", foreground=colors.INFO)
        self.log_box.tag_config("log_warning", foreground=colors.WARNING)
        self.log_box.tag_config("log_error", foreground=colors.DANGER)
        self.log_box.tag_config("log_time", foreground=colors.TEXT_MUTED)
        self.log_box.tag_config("log_message", foreground=colors.TEXT_PRIMARY)
        self.log_box.pack(fill="both", expand=True, padx=6, pady=5)

    def clear_logs(self):
        self.log_box.delete("1.0", "end")
