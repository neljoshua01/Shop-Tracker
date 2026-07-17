import customtkinter as ctk

from datetime import datetime

from ui import colors, fonts

from controllers.tracker_controller import TrackerController

from ui.components.sidebar import Sidebar
from ui.components.dashboard_header import DashboardHeader
from ui.components.status_bar import StatusBar
from ui.components.dashboard_stats import DashboardStats
from ui.components.topbar import TopBar
from ui.components.product_list import ProductList


class MainWindow(ctk.CTk):

    def __init__(self):
        super().__init__()

        self.title("Shopee Price Tracker")
        self.geometry("1280x880")
        self.minsize(1100, 800)

        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        self.configure(fg_color=colors.BACKGROUND)

        self.sidebar = Sidebar(self)
        self.sidebar.pack(
            side="left",
            fill="y"
        )

        self.main_frame = ctk.CTkFrame(
            self,
            fg_color=colors.BACKGROUND
        )

        self.main_frame.pack(
            side="left",
            fill="both",
            expand=True
        )

        self.build_ui(self.main_frame)

        self.controller = TrackerController(
            logger=self.log
        )

        self.controller.set_ui_callback(
            self.on_product_update
        )
    # =====================================================
    # Build Dashboard Layout
    # =====================================================
    def build_ui(self, parent):
        # ==================================================
        # Dashboard Header
        # ==================================================
        self.dashboard_header = DashboardHeader(parent)
        self.dashboard_header.pack(
            fill="x",
            padx=20,
            pady=(25, 10)
        )

        # ==================================================
        # Add Product Bar
        # ==================================================
        self.topbar = TopBar(
            parent,
            add_callback=self.start_monitoring
        )

        self.topbar.pack(
            fill="x",
            padx=20,
            pady=(5, 12)
        )

        # ==================================================
        # LIVE Status Bar
        # ==================================================
        self.status_bar = StatusBar(parent)

        self.status_bar.pack(
            fill="x",
            padx=20,
            pady=(0, 12)
        )

        # ==================================================
        # Dashboard Statistics
        # ==================================================
        self.stats = DashboardStats(parent)

        self.stats.pack(
            fill="x",
            padx=20,
            pady=(0, 16)
        )

        # ==================================================
        # Products Section
        # ==================================================
        products_header = ctk.CTkLabel(
            parent,
            text="Products Being Monitored",
            font=fonts.HEADING,
            text_color=colors.TEXT_PRIMARY
        )

        products_header.pack(
            anchor="w",
            padx=20,
            pady=(0, 6)
        )

        self.products_frame = ProductList(
            parent,
            stop_callback=self.stop_monitoring,
            fg_color="transparent",
            height=260
        )

        self.products_frame.pack(
            fill="x",
            padx=20,
            pady=(0, 12)
        )

        # ==========================
        # Activity Logs + Quick Actions
        # ==========================
        bottom_frame = ctk.CTkFrame(
            parent,
            fg_color="transparent"
        )

        bottom_frame.pack(
            fill="x",
            padx=20,
            pady=(0, 12)
        )

        bottom_frame.grid_columnconfigure(0, weight=1)
        bottom_frame.grid_columnconfigure(1, weight=1)

        self.build_activity_logs(bottom_frame)
        self.build_quick_actions(bottom_frame)

        # ==================================================
        # Initial Logs
        # ==================================================
        self.log("Application Started")
        self.log("Waiting for product URL...")

    def build_activity_logs(self, parent):
        logs_frame = ctk.CTkFrame(
            parent,
            fg_color=colors.CARD,
            border_width=1,
            border_color=colors.BORDER,
            corner_radius=8
        )

        logs_frame.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=(0, 8)
        )

        header = ctk.CTkFrame(
            logs_frame,
            fg_color="transparent"
        )

        header.pack(fill="x", padx=18, pady=(12, 6))

        logs_label = ctk.CTkLabel(
            header,
            text="Activity Logs",
            font=fonts.HEADING,
            text_color=colors.TEXT_PRIMARY
        )

        logs_label.pack(
            side="left"
        )

        ctk.CTkButton(
            header,
            text="View All Logs",
            width=110,
            height=30,
            fg_color=colors.PRIMARY_SOFT,
            hover_color=colors.CARD_HOVER,
            text_color=colors.PRIMARY_HOVER,
            command=lambda: None
        ).pack(
            side="right"
        )

        self.log_box = ctk.CTkTextbox(
            logs_frame,
            height=118,
            font=fonts.LOG,
            fg_color="transparent",
            border_width=0,
            text_color=colors.TEXT_SECONDARY
        )

        self.log_box.tag_config("log_success", foreground=colors.SUCCESS)
        self.log_box.tag_config("log_info", foreground=colors.INFO)
        self.log_box.tag_config("log_warning", foreground=colors.WARNING)
        self.log_box.tag_config("log_error", foreground=colors.DANGER)
        self.log_box.tag_config("log_time", foreground=colors.TEXT_SECONDARY)
        self.log_box.tag_config("log_message", foreground=colors.TEXT_PRIMARY)

        self.log_box.pack(
            fill="x",
            padx=18,
            pady=(0, 14)
        )

    def build_quick_actions(self, parent):
        actions_frame = ctk.CTkFrame(
            parent,
            fg_color=colors.CARD,
            border_width=1,
            border_color=colors.BORDER,
            corner_radius=8
        )

        actions_frame.grid(
            row=0,
            column=1,
            sticky="nsew",
            padx=(8, 0)
        )

        ctk.CTkLabel(
            actions_frame,
            text="Quick Actions",
            font=fonts.HEADING,
            text_color=colors.TEXT_PRIMARY
        ).pack(anchor="w", padx=18, pady=(12, 10))

        tiles = ctk.CTkFrame(
            actions_frame,
            fg_color="transparent"
        )

        tiles.pack(fill="x", padx=14, pady=(0, 14))

        tile_data = [
            ("♧", "Add Alert", "Get notified on price drops"),
            ("ϟ", "Flash Sale Calendar", "View upcoming flash sales"),
            ("🛒", "Cart Settings", "Manage auto checkout cart")
        ]

        for index, (icon, title, subtitle) in enumerate(tile_data):
            tile = ctk.CTkButton(
                tiles,
                text=f"{icon}\n\n{title}\n{subtitle}",
                height=100,
                fg_color=colors.SURFACE,
                hover_color=colors.CARD_HOVER,
                border_width=1,
                border_color=colors.BORDER,
                text_color=colors.TEXT_PRIMARY,
                font=fonts.BUTTON,
                command=lambda: None
            )

            tile.grid(
                row=0,
                column=index,
                sticky="nsew",
                padx=6
            )

            tiles.grid_columnconfigure(index, weight=1)

    def log(self, message):

         self.after(
             0,
            lambda: self._append_log(message)
        )

    def _append_log(self, message):
        timestamp = datetime.now().strftime("%I:%M:%S %p").lstrip("0")
        status_tag = self.get_log_status_tag(message)

        self.log_box.insert("end", "● ", status_tag)
        self.log_box.insert("end", f"{timestamp}   ", "log_time")
        self.log_box.insert("end", f"{message}\n", "log_message")

        self.log_box.see("end")

    def get_log_status_tag(self, message):
        normalized_message = message.lower()

        if any(word in normalized_message for word in ("error", "failed", "invalid")):
            return "log_error"

        if any(word in normalized_message for word in ("discount", "low stock", "warning")):
            return "log_warning"

        if any(word in normalized_message for word in ("refresh", "checking", "waiting")):
            return "log_info"

        return "log_success"
    
    def start_monitoring(self):

        url = self.topbar.get_url()
        success, message = self.controller.add_product(url)

        self.log(message)

        if not success:
            self.topbar.focus_url()
            return

        self.topbar.clear()

        self.status_bar.update_timestamp()

    def on_product_update(self, product):

        def update():

            #
            # Update only this product card
            #
            self.products_frame.update_product(product)

            #
            # Footer
            #
            self.status_bar.update_timestamp()

        self.after(
            0,
            update
        )

    def refresh_products(self):

        products = self.controller.get_products()

        #
        # Remove cards that no longer exist
        #
        current_urls = {
            product.url
            for product in products
        }

        for url in list(self.products_frame.cards.keys()):

            if url not in current_urls:
                self.products_frame.remove_product(url)

        #
        # Add or update cards
        #
        for product in products:

            self.products_frame.update_product(product)

        #
        # Update footer
        #
        self.status_bar.update_product_count(
            len(products)
        )

        self.status_bar.update_timestamp()

    def stop_monitoring(self, product):

        success, message = self.controller.remove_product(product)

        self.log(message)

        if not success:
            return

        #
        # Remove this card immediately
        #
        self.products_frame.remove_product(product.url)

        #
        # Update counters
        #
        self.status_bar.update_product_count(
            len(self.controller.get_products())
        )

        self.stats.products.update(
            str(len(self.controller.get_products()))
        )

        self.status_bar.update_timestamp()
