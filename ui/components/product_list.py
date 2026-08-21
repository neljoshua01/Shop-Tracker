import customtkinter as ctk
from types import SimpleNamespace
from urllib.parse import urlparse

from ui.components.product_card import ProductCard
from ui import colors, fonts


class ProductList(ctk.CTkScrollableFrame):
    def __init__(self, master, stop_callback=None, **kwargs):
        super().__init__(master, **kwargs)
        self.stop_callback = stop_callback
        self.set_target_callback = None
        self.cards = {}
        self.profile_cards = {}

        self.header = ctk.CTkFrame(
            self, fg_color=colors.SURFACE, border_width=1,
            border_color=colors.DIVIDER, corner_radius=6, height=44,
        )
        self.header.pack(fill="x", padx=4, pady=(4, 5))
        self.header.pack_propagate(False)

        columns = [
            "Product", "Stock", "Auto Checkout", "Target Price",
            "Current Price", "Last Checked", "Actions",
        ]
        weights = [4, 2, 2, 2, 2, 2, 1]
        header_content = ctk.CTkFrame(self.header, fg_color="transparent")
        header_content.pack(fill="both", expand=True, padx=8, pady=6)
        for index, weight in enumerate(weights):
            header_content.grid_columnconfigure(index, weight=weight)
        header_content.grid_rowconfigure(0, weight=1)
        for index, label in enumerate(columns):
            ctk.CTkLabel(
                header_content, text=label, font=fonts.SMALL_BOLD,
                text_color=colors.TEXT_MUTED, anchor="w", fg_color="transparent",
            ).grid(row=0, column=index, sticky="w", padx=(4, 4))

        self.empty_state = ctk.CTkFrame(
            self, fg_color=colors.SURFACE, border_width=1,
            border_color=colors.DIVIDER, corner_radius=8,
        )
        content_box = ctk.CTkFrame(self.empty_state, fg_color="transparent")
        content_box.pack(pady=24, padx=14)
        ctk.CTkFrame(content_box, width=3, height=24, fg_color=colors.INFO, corner_radius=2).pack(pady=(0, 6))
        self.empty_icon = ctk.CTkLabel(content_box, text="▣", font=(fonts.FONT_FAMILY, 20), text_color=colors.INFO)
        self.empty_icon.pack(pady=(0, 6))
        self.empty_title = ctk.CTkLabel(
            content_box, text="No products being monitored", font=fonts.SUBTITLE, text_color=colors.TEXT_PRIMARY
        )
        self.empty_title.pack()
        self.empty_description = ctk.CTkLabel(
            content_box,
            text="Add a Shopee product above to start monitoring its price and stock.",
            font=fonts.SMALL, text_color=colors.TEXT_SECONDARY,
        )
        self.empty_description.pack(pady=(4, 0))
        self.empty_state.pack(fill="x", padx=4, pady=3)

    def update_product(self, product):
        self.empty_state.pack_forget()
        if product.url in self.cards:
            self.cards[product.url].update_data(product)
            return
        card = ProductCard(
            self, product, stop_callback=self.stop_callback, set_target_callback=self.set_target_callback
        )
        card.pack(fill="x", padx=4, pady=3)
        self.cards[product.url] = card

    def update_purchase_profile(self, profile, session, event=None):
        key = self._profile_key(profile)
        product = self._profile_view_model(profile, session, event=event)
        self.empty_state.pack_forget()

        if key in self.profile_cards:
            self.profile_cards[key].update_data(product)
            return

        card = ProductCard(self, product, stop_callback=None, set_target_callback=None)
        # Purchase Profile execution has its own coordinator/pipeline lifecycle;
        # its stop/target controls remain disabled until that runtime exposes a
        # safe profile-specific callback. Details remain an ordinary ProductCard action.
        card.checkout_switch.configure(state="disabled")
        card.target_entry.configure(state="disabled")
        card.lock_button.configure(state="disabled")
        card.pack(fill="x", padx=4, pady=3)
        self.profile_cards[key] = card

    @staticmethod
    def _profile_key(profile):
        variation = profile.selected_variations[0]
        return f"profile://{profile.product.shop_id}:{profile.product.item_id}:{variation.model_id}"

    @staticmethod
    def _normalize_profile_image(image, product_url):
        if not image:
            return ""

        image = str(image).strip()
        if image.startswith(("http://", "https://")):
            return image
        if image.startswith("//"):
            return "https:" + image

        host = (urlparse(product_url).hostname or "").lower()
        market = "ph"
        if host.startswith("shopee."):
            suffix = host.split(".", 1)[1]
            market = suffix.split(".", 1)[0] or market
        elif ".shopee." in host:
            market = host.split(".shopee.", 1)[0] or market

        return f"https://down-{market}.img.susercontent.com/file/{image.lstrip('/')}"

    @staticmethod
    def _profile_view_model(profile, session, event=None):
        variation = profile.selected_variations[0]
        status = session.status.value.replace("_", " ").upper()
        runtime_status = str(event).replace("_", " ").upper() if event else status

        if status == "COMPLETED":
            stock = "COMPLETED"
        elif status == "FAILED":
            stock = "FAILED"
        else:
            stock = "IN STOCK" if variation.has_stock else "OUT OF STOCK"

        discount = ""
        if variation.price_before_discount and variation.price_before_discount > variation.price:
            discount = f"-{round((1 - variation.price / variation.price_before_discount) * 100)}%"

        is_monitoring = event != "MONITORING_STOPPED" and status not in {"COMPLETED", "FAILED"}
        return SimpleNamespace(
            url=ProductList._profile_key(profile),
            shop_id=str(profile.product.shop_id),
            item_id=str(profile.product.item_id),
            name=profile.product.product_name,
            image_url=ProductList._normalize_profile_image(
                profile.product.image,
                profile.product.product_url,
            ),
            current_price=variation.price,
            original_price=variation.price_before_discount,
            discount=discount,
            stock=stock,
            target_price=profile.target_price,
            target_locked=profile.lock_selected_variations,
            auto_checkout=profile.auto_checkout,
            purchased=status == "COMPLETED",
            is_monitoring=is_monitoring,
            runtime_status=runtime_status,
        )

    def remove_product(self, url):
        card = self.cards.pop(url, None)
        if card:
            card.destroy()
        if not self.cards and not self.profile_cards:
            self.empty_state.pack(fill="x", padx=4, pady=3)

    def remove_purchase_profile(self, profile_key):
        card = self.profile_cards.pop(profile_key, None)
        if card:
            card.destroy()
        if not self.cards and not self.profile_cards:
            self.empty_state.pack(fill="x", padx=4, pady=3)

    def clear(self):
        for card in self.cards.values():
            card.destroy()
        for card in self.profile_cards.values():
            card.destroy()
        self.cards.clear()
        self.profile_cards.clear()
        self.empty_state.pack(fill="x", padx=4, pady=3)

    def count(self):
        return len(self.cards)
