import customtkinter as ctk
import threading

from ui import colors, fonts
from ui.windows.product_details import ProductDetailsWindow
from ui import icons


def truncate_name(name, max_length=20):
    if not name:
        return ""
    name = str(name)
    if len(name) <= max_length:
        return name
    return name[:max_length - 1].rstrip() + "…"


class ProductCard(ctk.CTkFrame):

    def __init__(self, master, product, stop_callback=None, image=None, set_target_callback=None):
        super().__init__(
            master,
            fg_color=colors.CARD,
            border_width=1,
            border_color=colors.BORDER,
            corner_radius=8
        )
        self.product = product
        self.stop_callback = stop_callback
        self.set_target_callback = set_target_callback
        self.image = image
        self.name_label = None
        self.runtime_status_label = None
        self.stock_label = None
        self.price_label = None
        self.discount_label = None
        self.last_checked_label = None
        self.target_entry = None
        self.checkout_switch = None
        self.lock_button = None
        self.build_ui()

    def build_ui(self):
        for index, weight in enumerate([6, 2, 2, 2, 2, 2, 1]):
            self.grid_columnconfigure(index, weight=weight)
        self.build_product()
        self.build_stock()
        self.build_auto_checkout()
        self.build_target_price()
        self.build_current_price()
        self.build_last_checked()
        self.build_actions()

    def build_product(self):
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.grid(row=0, column=0, sticky="nsew", padx=(16, 10), pady=12)
        thumbnail = ctk.CTkFrame(
            frame, width=56, height=56, fg_color=colors.SURFACE_LIGHT,
            border_width=1, border_color=colors.BORDER, corner_radius=8
        )
        thumbnail.pack(side="left")
        thumbnail.pack_propagate(False)
        self.thumbnail_label = ctk.CTkLabel(thumbnail, text="📱", font=fonts.PRODUCT_PRICE)
        self.thumbnail_label.pack(expand=True)
        self.load_thumbnail()
        info = ctk.CTkFrame(frame, fg_color="transparent")
        info.pack(side="left", padx=(12, 0), fill="x", expand=True)
        self.name_label = ctk.CTkLabel(
            info, text=truncate_name(self.product.name), font=fonts.SUBTITLE,
            text_color=colors.TEXT_PRIMARY, anchor="w", wraplength=220, justify="left"
        )
        self.name_label.pack(anchor="w")
        ctk.CTkLabel(info, text="Shopee", font=fonts.SMALL, text_color=colors.TEXT_SECONDARY).pack(anchor="w")
        self.runtime_status_label = ctk.CTkLabel(
            info, text="", font=fonts.SMALL_BOLD, text_color=colors.INFO, anchor="w"
        )
        self.runtime_status_label.pack(anchor="w")
        self._update_runtime_status_label()

    def build_stock(self):
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.grid(row=0, column=1, sticky="nsew", padx=8, pady=12)
        ctk.CTkLabel(frame, text="Stock", font=fonts.SMALL, text_color=colors.TEXT_SECONDARY).pack()
        stock_text, badge_bg, badge_color = self.stock_badge_style(self.product.stock)
        self.stock_label = ctk.CTkLabel(
            frame, text=stock_text, height=28, corner_radius=14, font=fonts.BADGE,
            fg_color=badge_bg, text_color=badge_color
        )
        self.stock_label.pack(pady=(6, 0))

    def build_auto_checkout(self):
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.grid(row=0, column=2, sticky="nsew", padx=8, pady=12)
        ctk.CTkLabel(frame, text="Auto Checkout", font=fonts.SMALL, text_color=colors.TEXT_SECONDARY).pack()
        self.checkout_switch = ctk.CTkSwitch(frame, text="", width=42, command=self.toggle_auto_checkout)
        self.checkout_switch.pack(pady=(6, 0))
        if getattr(self.product, "auto_checkout", False):
            self.checkout_switch.select()

    def toggle_auto_checkout(self):
        enabled = bool(self.checkout_switch.get())
        self.product.auto_checkout = enabled
        if self.set_target_callback:
            self.set_target_callback(
                self.product, self.product.target_price, enabled,
                getattr(self.product, "target_locked", False)
            )

    def toggle_target_lock(self):
        if getattr(self.product, "target_locked", False):
            self.product.target_locked = False
            self.product.target_price = None
            self.target_entry.configure(state="normal", border_color=colors.BORDER, border_width=1)
            self.lock_button.configure(text="Lock")
        else:
            try:
                value = self.target_entry.get().replace(",", "").replace("₱", "").strip()
                self.product.target_price = float(value)
            except ValueError:
                self.product.target_price = None
                self.target_entry.configure(border_color=colors.DANGER, border_width=2)
                return
            self.product.target_locked = True
            self.target_entry.configure(state="disabled", border_color=colors.SUCCESS, border_width=2)
            self.lock_button.configure(text="Unlock")
        if self.set_target_callback:
            self.set_target_callback(
                self.product, self.product.target_price, self.product.auto_checkout,
                self.product.target_locked
            )

    def build_target_price(self):
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.grid(row=0, column=3, sticky="nsew", padx=8, pady=12)
        ctk.CTkLabel(frame, text="Target Price", font=fonts.SMALL, text_color=colors.TEXT_SECONDARY).pack()
        input_row = ctk.CTkFrame(frame, fg_color="transparent")
        input_row.pack(pady=(6, 0))
        self.target_entry = ctk.CTkEntry(input_row, width=90, placeholder_text="₱70,000")
        self.target_entry.pack(side="left", padx=(0, 6))
        self.lock_button = ctk.CTkButton(input_row, text="Lock", width=64, height=28, command=self.toggle_target_lock)
        self.lock_button.pack(side="left")
        if getattr(self.product, "target_price", None):
            self.target_entry.insert(0, str(self.product.target_price))
        if getattr(self.product, "target_locked", False):
            self.target_entry.configure(state="disabled", border_color=colors.SUCCESS, border_width=2)
            self.lock_button.configure(text="Unlock")

    def build_current_price(self):
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.grid(row=0, column=4, sticky="nsew", padx=8, pady=12)
        ctk.CTkLabel(frame, text="Current Price", font=fonts.SMALL, text_color=colors.TEXT_SECONDARY).pack()
        price_row = ctk.CTkFrame(frame, fg_color="transparent")
        price_row.pack(pady=(4, 0))
        self.price_label = ctk.CTkLabel(price_row, text=str(self.product.current_price), font=fonts.SUBTITLE, text_color=colors.TEXT_PRIMARY)
        self.price_label.pack(side="left")
        badge_bg, badge_color = self.discount_badge_style(self.product.discount)
        self.discount_label = ctk.CTkLabel(
            price_row, text=str(self.product.discount), width=44, height=20, corner_radius=10,
            font=fonts.SMALL_BOLD, fg_color=badge_bg, text_color=badge_color
        )
        self.discount_label.pack(side="left", padx=(6, 0))

    def build_last_checked(self):
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.grid(row=0, column=5, sticky="nsew", padx=8, pady=12)
        ctk.CTkLabel(frame, text="Last Checked", font=fonts.SMALL, text_color=colors.TEXT_SECONDARY).pack()
        self.last_checked_label = ctk.CTkLabel(frame, text="Just now", font=fonts.BODY, text_color=colors.TEXT_PRIMARY)
        self.last_checked_label.pack(pady=(8, 0))

    def build_actions(self):
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.grid(row=0, column=6, sticky="nsew", padx=(8, 16), pady=12)
        button_stack = ctk.CTkFrame(frame, fg_color="transparent")
        button_stack.pack(expand=True)

        details_icon = icons.load_icon(
            icons.PRODUCT,
            colors.SUCCESS,
            icons.SIZE_SMALL,
        )
        self.details_button = ctk.CTkButton(
            button_stack, text="", width=36, height=32, fg_color="transparent",
            hover_color=colors.CARD_HOVER, border_width=1, border_color=colors.SUCCESS,
            image=details_icon, command=self.open_details
        )
        self.details_button.pack(pady=(0, 8))

        pause_icon = icons.load_icon(
            icons.PAUSE,
            colors.DANGER,
            icons.SIZE_SMALL,
        )
        self.stop_button = ctk.CTkButton(
            button_stack, text="", width=36, height=32, fg_color="transparent",
            hover_color=colors.DANGER_BG, border_width=1, border_color=colors.DANGER,
            image=pause_icon, command=self.stop_monitoring
        )
        self.stop_button.pack()

    def stock_badge_style(self, value):
        stock_value = str(value).upper()
        if stock_value == "IN STOCK":
            return "IN STOCK", colors.SUCCESS_BG, colors.SUCCESS
        if stock_value == "LOW STOCK":
            return "LOW STOCK", colors.WARNING_BG, colors.WARNING
        if stock_value == "OUT OF STOCK":
            return "OUT OF STOCK", colors.DANGER_BG, colors.DANGER
        return stock_value or "--", colors.CARD_HOVER, colors.TEXT_SECONDARY

    def discount_badge_style(self, discount):
        discount = str(discount)
        if discount.startswith("-"):
            return colors.SUCCESS_BG, colors.SUCCESS
        if discount.startswith("+"):
            return colors.DANGER_BG, colors.DANGER
        return colors.CARD_HOVER, colors.TEXT_SECONDARY

    def _update_runtime_status_label(self):
        status = getattr(self.product, "runtime_status", None)
        if not status:
            status = "MONITORING" if getattr(self.product, "is_monitoring", False) else ""
        self.runtime_status_label.configure(
            text=str(status).replace("_", " ").upper(),
            text_color=self.runtime_status_color(status),
        )

    @staticmethod
    def runtime_status_color(status):
        value = str(status).lower()
        if value in {"completed", "running", "monitoring", "in_cart"}:
            return colors.SUCCESS
        if value in {"failed", "error"}:
            return colors.DANGER
        if value in {"starting", "preparing", "adding_to_cart", "checking_out", "triggered"}:
            return colors.WARNING
        return colors.INFO

    def update_data(self, product):
        self.product = product
        self.load_thumbnail()
        self.name_label.configure(text=truncate_name(product.name))
        self._update_runtime_status_label()
        self.price_label.configure(text=str(product.current_price))
        badge_bg, badge_color = self.discount_badge_style(product.discount)
        self.discount_label.configure(text=str(product.discount), fg_color=badge_bg, text_color=badge_color)
        stock_text, stock_bg, stock_color = self.stock_badge_style(product.stock)
        self.stock_label.configure(text=stock_text, fg_color=stock_bg, text_color=stock_color)
        self.last_checked_label.configure(text="Just now")

    def stop_monitoring(self):
        if self.stop_callback:
            self.stop_callback(self.product)

    def open_details(self):
        ProductDetailsWindow(self, self.product)

    def load_thumbnail(self):
        url = getattr(self.product, "image_url", "")
        if not url:
            return
        if not str(url).startswith(("http://", "https://")):
            return
        threading.Thread(target=self._fetch_thumbnail, args=(url,), daemon=True).start()

    def _fetch_thumbnail(self, url):
        try:
            import requests
            from PIL import Image
            from io import BytesIO
            if url.startswith("//"):
                url = "https:" + url
            response = requests.get(url, timeout=6)
            response.raise_for_status()
            pil_image = Image.open(BytesIO(response.content)).convert("RGB")
            pil_image = pil_image.resize((56, 56))
            ctk_image = ctk.CTkImage(light_image=pil_image, dark_image=pil_image, size=(56, 56))
            try:
                self.after(0, self._apply_thumbnail, ctk_image)
            except Exception:
                pass
        except Exception as e:
            print(f"[ProductCard] Thumbnail load failed: {e}")

    def _apply_thumbnail(self, ctk_image):
        if not self.winfo_exists():
            return
        self.thumbnail_label.configure(image=ctk_image, text="")
        self.thumbnail_label.image = ctk_image
