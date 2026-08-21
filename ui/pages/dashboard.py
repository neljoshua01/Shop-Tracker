import customtkinter as ctk

from ui import colors, fonts, icons

from ui.components.dashboard_header import DashboardHeader
from ui.components.dashboard_stats import DashboardStats
from ui.components.topbar import TopBar
from ui.components.status_bar import StatusBar
from ui.components.product_list import ProductList


class DashboardPage(ctk.CTkFrame):
    """Dashboard presentation layer; live data still comes from MainWindow/controller."""

    def __init__(self, master, start_monitoring_callback, stop_monitoring_callback, purchase_profile_callback=None, stop_purchase_profile_callback=None):
        super().__init__(master, fg_color=colors.BACKGROUND)
        self.start_monitoring_callback = start_monitoring_callback
        self.stop_monitoring_callback = stop_monitoring_callback
        self.purchase_profile_callback = purchase_profile_callback
        self.stop_purchase_profile_callback = stop_purchase_profile_callback
        self.engine_state = "IDLE"
        self.purchase_state = None
        self.build_ui()

    def build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=0)
        self.grid_rowconfigure(3, weight=1)
        self.grid_rowconfigure(4, weight=0)
        content_pad = 18

        header_row = ctk.CTkFrame(self, fg_color="transparent")
        header_row.grid(row=0, column=0, sticky="ew", padx=content_pad, pady=(14, 8))
        header_row.grid_columnconfigure(0, weight=1)
        self.dashboard_header = DashboardHeader(header_row)
        self.dashboard_header.grid(row=0, column=0, sticky="w")
        self.build_engine_status(header_row)

        self.topbar = TopBar(self, add_callback=self.start_monitoring_callback, purchase_profile_callback=self.purchase_profile_callback)
        self.status_bar = StatusBar(self)
        self.status_bar.grid(row=1, column=0, sticky="ew", padx=content_pad, pady=(0, 9))
        self.stats = DashboardStats(self)
        self.stats.grid(row=2, column=0, sticky="ew", padx=content_pad, pady=(0, 11))

        workspace = ctk.CTkFrame(self, fg_color="transparent")
        workspace.grid(row=3, column=0, sticky="nsew", padx=content_pad, pady=(0, 9))
        workspace.grid_columnconfigure(0, weight=3, uniform="workspace")
        workspace.grid_columnconfigure(1, weight=1, uniform="workspace")
        workspace.grid_rowconfigure(0, weight=0)
        workspace.grid_rowconfigure(1, weight=1)
        self.build_engine_panel(workspace)
        self.build_products_panel(workspace)
        self.build_pipeline_panel(workspace)

        bottom = ctk.CTkFrame(self, fg_color="transparent", height=172)
        bottom.grid(row=4, column=0, sticky="ew", padx=content_pad, pady=(0, 9))
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
            parent, fg_color="transparent", border_width=1, border_color=colors.BORDER,
            corner_radius=14, width=210, height=52,
        )
        engine_status.grid(row=0, column=1, sticky="e", padx=(12, 0))
        engine_status.grid_propagate(False)
        engine_status.grid_columnconfigure(0, weight=1)
        engine_status.grid_rowconfigure(0, weight=1)
        text_container = ctk.CTkFrame(engine_status, fg_color="transparent")
        text_container.grid(row=0, column=0, sticky="w", padx=(14, 14))
        text_container.grid_columnconfigure(1, weight=1)
        self.engine_status_dot = ctk.CTkFrame(text_container, width=8, height=8, fg_color=colors.INFO, corner_radius=4)
        self.engine_status_dot.grid(row=0, column=0, padx=(0, 8), pady=(2, 0), sticky="w")
        self.engine_status_dot.grid_propagate(False)
        ctk.CTkLabel(
            text_container, text="Engine Status", font=fonts.SMALL_BOLD,
            text_color=colors.TEXT_PRIMARY, anchor="w", height=18,
        ).grid(row=0, column=1, sticky="w")
        self.engine_status_secondary = ctk.CTkLabel(
            text_container, text="Idle", font=fonts.SMALL,
            text_color=colors.TEXT_SECONDARY, anchor="w", height=14,
        )
        self.engine_status_secondary.grid(row=1, column=1, sticky="w", pady=(2, 0))

    def panel(self, parent, row, column, title, subtitle=None, action_text=None, action_command=None, title_icon=None, title_icon_color=None):
        frame = ctk.CTkFrame(parent, fg_color=colors.CARD, border_width=1, border_color=colors.BORDER, corner_radius=9)
        frame.grid(row=row, column=column, sticky="nsew", padx=(0, 9) if column == 0 else 0, pady=0)
        header = ctk.CTkFrame(frame, fg_color="transparent", height=38)
        header.pack(fill="x", padx=14, pady=(7, 0))
        header.pack_propagate(False)
        if title_icon is not None:
            icon_image = icons.load_icon(title_icon, title_icon_color or colors.TEXT_PRIMARY, (30, 30))
            ctk.CTkLabel(header, text="", image=icon_image).pack(side="left", padx=(0, 7), anchor="center")
        ctk.CTkLabel(header, text=title, font=fonts.HEADING, text_color=colors.TEXT_PRIMARY).pack(side="left", anchor="center")
        if action_text and action_command:
            ctk.CTkButton(
                header, text=action_text, command=action_command, width=126, height=28,
                corner_radius=6, fg_color=colors.PRIMARY, hover_color=colors.PRIMARY_HOVER,
                border_width=1, border_color=colors.PRIMARY_HOVER, font=fonts.SMALL_BOLD,
                text_color=colors.TEXT_PRIMARY,
            ).pack(side="right", anchor="center")
        elif subtitle:
            subtitle_label = ctk.CTkLabel(
                header, text=subtitle, font=fonts.SMALL_BOLD,
                text_color=colors.INFO if "LIVE" in subtitle else colors.TEXT_MUTED,
            )
            subtitle_label.pack(side="right", anchor="center")
            frame._header_subtitle_label = subtitle_label
        return frame

    def build_engine_panel(self, parent):
        frame = self.panel(parent, 0, 0, "Monitoring Engine", "●  IDLE", title_icon=icons.MONITORING_ENGINE, title_icon_color=colors.INFO)
        self.engine_panel_status = getattr(frame, "_header_subtitle_label", None)
        self.engine_activity_label = ctk.CTkLabel(
            frame, text="Waiting for monitoring activity", font=fonts.SMALL, text_color=colors.TEXT_SECONDARY
        )
        self.engine_activity_label.pack(anchor="w", padx=14, pady=(0, 8))
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
                modules, fg_color=colors.SURFACE, border_width=1, border_color=colors.DIVIDER,
                corner_radius=7, height=64,
            )
            card.grid(row=0, column=index, sticky="ew", padx=(0, 7) if index < 2 else 0)
            card.grid_propagate(False)
            icon_box = ctk.CTkFrame(
                card, width=36, height=36,
                fg_color=colors.PRIMARY_SOFT if accent != colors.INFO else colors.INFO_BG,
                border_width=1, border_color=accent, corner_radius=7,
            )
            icon_box.place(x=8, y=14)
            icon_box.grid_propagate(False)
            icon_image = icons.load_icon(icon, accent, icons.SIZE_LARGE)
            ctk.CTkLabel(icon_box, text="", image=icon_image).place(relx=0.5, rely=0.5, anchor="center")
            text_container = ctk.CTkFrame(card, fg_color="transparent")
            text_container.place(x=53, y=9)
            ctk.CTkLabel(
                text_container, text=title, font=fonts.SMALL_BOLD,
                text_color=colors.TEXT_PRIMARY, anchor="w", height=18,
            ).pack(anchor="w")
            ctk.CTkLabel(
                text_container, text=text, font=fonts.SMALL,
                text_color=colors.TEXT_MUTED, anchor="w", height=16,
            ).pack(anchor="w", pady=(1, 0))

    def build_products_panel(self, parent):
        frame = self.panel(parent, 1, 0, "Active Products", action_text="Add Purchase Profile", action_command=self.purchase_profile_callback)
        frame.grid_configure(pady=(9, 0))
        self.products_frame = ProductList(
            frame,
            stop_callback=self.stop_monitoring_callback,
            purchase_stop_callback=self.stop_purchase_profile_callback,
            fg_color=colors.SURFACE,
            border_width=1, border_color=colors.BORDER, corner_radius=8, height=190,
        )
        self.products_frame.pack(fill="both", expand=True, padx=9, pady=(0, 9))

    def build_pipeline_panel(self, parent):
        frame = self.panel(parent, 0, 1, "System Pipeline", "LIVE")
        frame.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=0)
        self.pipeline_header_status = getattr(frame, "_header_subtitle_label", None)
        pipeline = ctk.CTkFrame(frame, fg_color="transparent")
        pipeline.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        stages = [
            ("Shopee Product", "Input source", colors.INFO, icons.SHOPEE_API),
            ("Monitoring Controller", "Tracking state", colors.PRIMARY_HOVER, icons.STATE_MANAGER),
            ("Purchase Profile", "Purchase configuration", colors.PRIMARY, icons.PURCHASE_PROFILE),
            ("Monitoring / Purchase", "Existing application flow", colors.SUCCESS, icons.EXECUTION_ENGINE),
        ]
        self.pipeline_stage_labels = {}
        for row, (name, detail, accent, icon) in enumerate(stages):
            item = ctk.CTkFrame(pipeline, fg_color=colors.SURFACE, corner_radius=7, height=52)
            item.pack(fill="x", pady=4)
            item.pack_propagate(False)
            icon_box = ctk.CTkFrame(item, width=34, height=34, fg_color=colors.PRIMARY_SOFT, border_width=1, border_color=accent, corner_radius=7)
            icon_box.place(x=8, y=9)
            icon_image = icons.load_icon(icon, accent, icons.SIZE_SMALL)
            ctk.CTkLabel(icon_box, text="", image=icon_image).place(relx=0.5, rely=0.5, anchor="center")
            text_container = ctk.CTkFrame(item, fg_color="transparent")
            text_container.place(x=51, y=8)
            ctk.CTkLabel(text_container, text=name, font=fonts.SMALL_BOLD, text_color=colors.TEXT_PRIMARY, anchor="w").pack(anchor="w")
            detail_label = ctk.CTkLabel(text_container, text=detail, font=fonts.SMALL, text_color=colors.TEXT_SECONDARY, anchor="w")
            detail_label.pack(anchor="w", pady=(1, 0))
            self.pipeline_stage_labels[name] = (item, detail_label)

    def set_engine_state(self, state, error=None):
        state = str(state).upper()
        self.engine_state = state
        labels = {
            "IDLE": ("●  IDLE", "Waiting for monitoring activity", colors.INFO),
            "STARTING": ("●  STARTING", "Starting monitoring workers", colors.WARNING),
            "RUNNING": ("●  RUNNING", "Monitoring active", colors.SUCCESS),
            "STOPPING": ("●  STOPPING", "Stopping monitoring workers", colors.WARNING),
            "ERROR": ("●  ERROR", str(error) if error else "Monitoring error", colors.DANGER),
        }
        title, activity, accent = labels.get(state, (f"●  {state}", "Monitoring state", colors.INFO))
        if self.engine_panel_status:
            self.engine_panel_status.configure(text=title, text_color=accent)
        self.engine_status_secondary.configure(text=state.title(), text_color=accent)
        self.engine_status_dot.configure(fg_color=accent)
        self.engine_activity_label.configure(text=activity, text_color=accent)
        if self.pipeline_header_status:
            self.pipeline_header_status.configure(text="LIVE" if state == "RUNNING" else state, text_color=colors.SUCCESS if state == "RUNNING" else accent)
        controller_detail = {
            "IDLE": "Waiting for workers",
            "STARTING": "Starting workers",
            "RUNNING": "Monitoring active",
            "STOPPING": "Stopping workers",
            "ERROR": "Monitoring error",
        }.get(state, state.title())
        labels = self.pipeline_stage_labels.get("Monitoring Controller")
        if labels:
            _, detail_label = labels
            detail_label.configure(text=controller_detail, text_color=accent)
