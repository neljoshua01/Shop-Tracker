import customtkinter as ctk

from datetime import datetime

from ui import colors, fonts

from controllers.tracker_controller import TrackerController

from ui.components.sidebar import Sidebar
from ui.pages.dashboard import DashboardPage
from ui.pages.products import ProductsPage
from ui.pages.activity_logs import ActivityLogsPage
from ui.pages.alerts import AlertsPage
from ui.pages.settings import SettingsPage
from ui.windows.purchase_profile_dialog import PurchaseProfileDialog


class MainWindow(ctk.CTk):

    def __init__(self):
        super().__init__()

        self.title("Shopee Price Tracker")
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()

        width = int(screen_w * 0.90)
        height = int(screen_h * 0.90)

        self.geometry(f"{width}x{height}")

        self.minsize(1100, 800)

        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        self.configure(fg_color=colors.BACKGROUND)

        # =====================================================
        # Main Window Layout
        # =====================================================

        # Sidebar stays fixed
        self.grid_columnconfigure(0, weight=0)

        # Main content expands
        self.grid_columnconfigure(1, weight=1)

        # Full height
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        self.sidebar = Sidebar(
            self,
            nav_callback=self.handle_navigation
        )

        self.sidebar.grid(
            row=0,
            column=0,
            sticky="ns"
        )

        # Main Content
        self.main_frame = ctk.CTkFrame(
            self,
            fg_color=colors.BACKGROUND
        )

        self.main_frame.grid(
            row=0,
            column=1,
            sticky="nsew"
        )

        self.main_frame.grid_rowconfigure(0, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)

        self.dashboard_page = DashboardPage(
            self.main_frame,
            start_monitoring_callback=self.start_monitoring,
            stop_monitoring_callback=self.stop_monitoring,
            purchase_profile_callback=self.open_purchase_profile,
        )

        self.dashboard_page.grid(
            row=0,
            column=0,
            sticky="nsew"
        )

        self.products_page = ProductsPage(
            self.main_frame,
            stop_monitoring_callback=self.stop_monitoring
        )

        self.activity_logs_page = ActivityLogsPage(
            self.main_frame
        )

        self.alerts_page = AlertsPage(
            self.main_frame
        )

        self.settings_page = SettingsPage(
            self.main_frame
        )

        self.pages = {
            "Dashboard": self.dashboard_page,
            "Products": self.products_page,
            "Activity Logs": self.activity_logs_page,
            "Alerts &\nAuto Checkout": self.alerts_page,
            "Settings": self.settings_page,
        }

        self.topbar = self.dashboard_page.topbar
        self.status_bar = self.dashboard_page.status_bar
        self.stats = self.dashboard_page.stats
        self.products_frame = self.dashboard_page.products_frame
        self.log_box = self.dashboard_page.log_box

        self.controller = TrackerController(
            logger=self.log
        )

        self.controller.set_ui_callback(
            self.on_product_update
        )

        #
        # Receive Target Price / Auto Checkout changes.
        #

        self.products_frame.set_target_callback = (
            self.controller.set_target
        )
        #
        # Restore previous monitoring session
        #
        self.controller.load_products()

        #
        # Show restored products
        #
        self.refresh_products()

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

    def open_purchase_profile(self):
        PurchaseProfileDialog(self, on_save=self.save_purchase_profile)

    def save_purchase_profile(self, profile):
        session = self.controller.create_purchase_profile(profile)
        self.log(f"Purchase profile saved and started: {profile.product.product_name}")
        self.status_bar.update_timestamp()
        return session

    def on_product_update(self, product):

        def update():

            #
            # Update only this product card
            #
            self.products_frame.update_product(product)

            #
            # Live counters
            #
            count = len(self.controller.get_products())

            self.status_bar.update_product_count(count)

            self.stats.products.update(str(count))

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

    def handle_navigation(self, page):

        selected_page = self.pages.get(page)

        if selected_page is None:
            return

        for current_page in self.pages.values():
            current_page.grid_forget()

        selected_page.grid(
            row=0,
            column=0,
            sticky="nsew"
        )
