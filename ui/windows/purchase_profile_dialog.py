"""Dashboard dialog for creating a real V2 purchase profile."""

import threading
import customtkinter as ctk

from purchase.models.purchase_profile import PurchaseProfile
from purchase.models.trigger_condition import TriggerCondition
from purchase.services.product_loader import ProductLoader
from purchase.parser.url_parser import URLParser
from purchase.services.purchase_profile_service import PurchaseProfileService
from ui import colors, fonts


class PurchaseProfileDialog(ctk.CTkToplevel):
    def __init__(self, master, on_save):
        super().__init__(master)
        self.on_save = on_save
        self.product = None
        self.selected_variation = None
        self.quantity = 1
        self.option_vars = {}
        self.trigger_var = ctk.StringVar(value=TriggerCondition.PRICE_TARGET.value)
        self.auto_checkout_var = ctk.BooleanVar(value=False)
        self.lock_var = ctk.BooleanVar(value=True)

        self.title("Purchase Profile")
        self.geometry("860x760")
        self.minsize(760, 650)
        self.configure(fg_color=colors.BACKGROUND)
        self.transient(master)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self._build_ui()
        self._update_summary()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color=colors.CARD, corner_radius=0)
        header.pack(fill="x")
        ctk.CTkLabel(header, text="Purchase Profile", font=fonts.SUBTITLE,
                     text_color=colors.TEXT_PRIMARY).pack(side="left", padx=24, pady=(15, 2))
        ctk.CTkButton(header, text="×", width=36, height=30, fg_color="transparent",
                      hover_color=colors.CARD_HOVER, font=fonts.HEADING,
                      command=self.destroy).pack(side="right", padx=14, pady=12)
        ctk.CTkLabel(header, text="Create a monitoring profile for a Shopee product", font=fonts.SMALL,
                     text_color=colors.TEXT_SECONDARY).pack(anchor="w", padx=24, pady=(0, 14))

        self.scroll = ctk.CTkScrollableFrame(self, fg_color=colors.BACKGROUND)
        self.scroll.pack(fill="both", expand=True, padx=18, pady=12)
        self.scroll.grid_columnconfigure((0, 1), weight=1, uniform="columns")

        self.source_card = self._card(self.scroll, "1", "Product Source", "Load a Shopee product through Chrome")
        self.source_card.grid(row=0, column=0, sticky="new", padx=(0, 7), pady=(0, 10))
        self.info_card = self._card(self.scroll, "2", "Product Information", "Read only")
        self.info_card.grid(row=0, column=1, sticky="new", padx=(7, 0), pady=(0, 10))
        self.variation_card = self._card(self.scroll, "3", "Product Variations", "Select one available SKU")
        self.variation_card.grid(row=1, column=0, sticky="new", padx=(0, 7), pady=(0, 10))
        self.settings_card = self._card(self.scroll, "4", "Purchase Settings", "Monitoring and purchase rules")
        self.settings_card.grid(row=1, column=1, sticky="new", padx=(7, 0), pady=(0, 10))
        self.checkout_card = self._card(self.scroll, "5", "Auto Checkout", "Uses configured cart, payment, shipping, and OTP")
        self.checkout_card.grid(row=2, column=0, sticky="new", padx=(0, 7), pady=(0, 10))
        self.summary_card = self._card(self.scroll, "6", "Purchase Summary", "Updates as you configure the profile")
        self.summary_card.grid(row=2, column=1, sticky="new", padx=(7, 0), pady=(0, 10))

        self._build_source()
        self._build_info()
        self._build_variations()
        self._build_settings()
        self._build_checkout()
        self._build_summary()

        footer = ctk.CTkFrame(self, fg_color=colors.CARD, corner_radius=0)
        footer.pack(fill="x", side="bottom")
        self.error_label = ctk.CTkLabel(footer, text="", font=fonts.SMALL, text_color=colors.DANGER)
        self.error_label.pack(side="left", padx=20, pady=14)
        ctk.CTkButton(footer, text="Cancel", width=100, fg_color=colors.SURFACE_LIGHT,
                      hover_color=colors.CARD_HOVER, command=self.destroy).pack(side="right", padx=(8, 20), pady=12)
        self.save_button = ctk.CTkButton(footer, text="Save Purchase Profile", width=190,
                                         fg_color=colors.PRIMARY, hover_color=colors.PRIMARY_HOVER,
                                         command=self._save)
        self.save_button.pack(side="right", pady=12)

    def _card(self, parent, step, title, subtitle):
        card = ctk.CTkFrame(parent, fg_color=colors.CARD, border_width=1,
                            border_color=colors.BORDER, corner_radius=9)
        title_row = ctk.CTkFrame(card, fg_color="transparent")
        title_row.pack(fill="x", padx=15, pady=(12, 0))
        ctk.CTkLabel(title_row, text=step, width=20, height=20, corner_radius=10,
                     fg_color=colors.PRIMARY, font=fonts.SMALL_BOLD).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(title_row, text=title, font=fonts.BODY, text_color=colors.TEXT_PRIMARY).pack(side="left")
        ctk.CTkLabel(card, text=subtitle, font=fonts.SMALL, text_color=colors.TEXT_SECONDARY).pack(anchor="w", padx=15, pady=(2, 10))
        return card

    def _build_source(self):
        row = ctk.CTkFrame(self.source_card, fg_color="transparent")
        row.pack(fill="x", padx=15)
        self.url_entry = ctk.CTkEntry(row, placeholder_text="https://shopee.ph/...", height=38,
                                      fg_color=colors.INPUT, border_color=colors.BORDER, font=fonts.SMALL)
        self.url_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.load_button = ctk.CTkButton(row, text="Load Product", width=115, height=38,
                                         fg_color=colors.PRIMARY, hover_color=colors.PRIMARY_HOVER,
                                         command=self._load_product)
        self.load_button.pack(side="right")
        self.status_label = ctk.CTkLabel(self.source_card, text="Ready to load a product.", font=fonts.SMALL,
                                         text_color=colors.TEXT_SECONDARY, justify="left", wraplength=340)
        self.status_label.pack(anchor="w", padx=15, pady=(10, 14))

    def _build_info(self):
        self.info_labels = {}
        for label in ("Product Name", "Shop", "Product ID", "Current Price", "Stock"):
            row = ctk.CTkFrame(self.info_card, fg_color="transparent")
            row.pack(fill="x", padx=15, pady=3)
            ctk.CTkLabel(row, text=label, font=fonts.SMALL, text_color=colors.TEXT_SECONDARY).pack(side="left")
            value = ctk.CTkLabel(row, text="—", font=fonts.SMALL, text_color=colors.TEXT_PRIMARY, wraplength=180)
            value.pack(side="right")
            self.info_labels[label] = value
        ctk.CTkFrame(self.info_card, height=5, fg_color="transparent").pack()

    def _build_variations(self):
        self.variation_content = ctk.CTkFrame(self.variation_card, fg_color="transparent")
        self.variation_content.pack(fill="both", expand=True, padx=15, pady=(0, 14))
        self.variation_hint = ctk.CTkLabel(self.variation_content, text="Load a product to see its available variations.",
                                           font=fonts.SMALL, text_color=colors.TEXT_SECONDARY, wraplength=340)
        self.variation_hint.pack(anchor="w")

    def _build_settings(self):
        quantity = ctk.CTkFrame(self.settings_card, fg_color="transparent")
        quantity.pack(fill="x", padx=15)
        ctk.CTkLabel(quantity, text="Quantity", font=fonts.SMALL, text_color=colors.TEXT_PRIMARY).pack(side="left")
        ctk.CTkButton(quantity, text="−", width=30, height=28, fg_color=colors.SURFACE_LIGHT, command=lambda: self._change_quantity(-1)).pack(side="right")
        self.quantity_label = ctk.CTkLabel(quantity, text="1", width=30, font=fonts.BODY)
        self.quantity_label.pack(side="right", padx=5)
        ctk.CTkButton(quantity, text="+", width=30, height=28, fg_color=colors.SURFACE_LIGHT, command=lambda: self._change_quantity(1)).pack(side="right")

        ctk.CTkLabel(self.settings_card, text="Trigger (Monitoring Condition)", font=fonts.SMALL,
                     text_color=colors.TEXT_PRIMARY).pack(anchor="w", padx=15, pady=(12, 3))
        labels = [(TriggerCondition.TRACK_ONLY, "Track Only"), (TriggerCondition.PRICE_TARGET, "Price ≤ Target"),
                  (TriggerCondition.STOCK_AVAILABLE, "Stock Available"), (TriggerCondition.PRICE_AND_STOCK, "Both Price AND Stock")]
        for value, text in labels:
            ctk.CTkRadioButton(self.settings_card, text=text, variable=self.trigger_var, value=value.value,
                               font=fonts.SMALL, command=self._trigger_changed).pack(anchor="w", padx=15, pady=2)
        self.target_entry = ctk.CTkEntry(self.settings_card, placeholder_text="Target Price (₱)", height=34,
                                         fg_color=colors.INPUT, border_color=colors.BORDER)
        self.target_entry.pack(fill="x", padx=15, pady=(10, 5))
        self.target_entry.bind("<KeyRelease>", lambda _event: self._update_summary())
        self.polling_menu = ctk.CTkOptionMenu(self.settings_card, values=["5 seconds", "10 seconds", "30 seconds", "60 seconds"],
                                              fg_color=colors.SURFACE_LIGHT, button_color=colors.PRIMARY,
                                              command=lambda _value: self._update_summary())
        self.polling_menu.set("30 seconds")
        self.polling_menu.pack(fill="x", padx=15, pady=5)
        self.lock_switch = ctk.CTkCheckBox(self.settings_card, text="Lock selected variations", variable=self.lock_var,
                                           font=fonts.SMALL, command=self._update_summary)
        self.lock_switch.select()
        self.lock_switch.pack(anchor="w", padx=15, pady=(7, 12))

    def _build_checkout(self):
        self.auto_switch = ctk.CTkSwitch(self.checkout_card, text="Enable Auto Checkout", variable=self.auto_checkout_var,
                                         font=fonts.BODY, command=self._update_summary)
        self.auto_switch.pack(anchor="w", padx=15, pady=(0, 6))
        ctk.CTkLabel(self.checkout_card, text="When enabled, the existing purchase pipeline prepares cart and verifies checkout. Global Armed Mode remains the final safety gate.",
                     font=fonts.SMALL, text_color=colors.TEXT_SECONDARY, justify="left", wraplength=340).pack(anchor="w", padx=15, pady=(0, 14))

    def _build_summary(self):
        self.summary_label = ctk.CTkLabel(self.summary_card, text="", font=fonts.SMALL, text_color=colors.TEXT_PRIMARY,
                                          justify="left", anchor="w")
        self.summary_label.pack(fill="x", padx=15, pady=(0, 14))

    def _load_product(self):
        url = self.url_entry.get().strip()
        try:
            reference = URLParser.parse(url)
        except ValueError as exc:
            self._set_error(str(exc))
            return
        self._set_error("")
        self.load_button.configure(state="disabled")
        self.status_label.configure(text="Opening Chrome\nReading Product\nFetching browser API…", text_color=colors.INFO)
        threading.Thread(target=self._load_worker, args=(reference,), daemon=True).start()

    def _load_worker(self, reference):
        try:
            product = ProductLoader().load(reference)
            if product is None:
                raise RuntimeError("Shopee returned no product information.")
            # The browser-loaded response can expose a canonical share
            # URL; retain the user-entered PDP URL for the purchase flow.
            product.product_url = reference.url
            self.after(0, lambda: self._product_loaded(product))
        except Exception as exc:
            self.after(0, lambda: self._product_failed(str(exc)))

    def _product_loaded(self, product):
        self.product = product
        self.load_button.configure(state="normal")
        self.status_label.configure(text="✓ Product Loaded\nParsing Variations complete.", text_color=colors.SUCCESS)
        variations = product.available_variations
        prices = [v.price for v in variations if v.price is not None]
        stock = sum(1 for v in variations if v.has_stock)
        values = {"Product Name": product.product_name, "Shop": product.shop_name or "—",
                  "Product ID": str(product.item_id), "Current Price": f"₱{min(prices):,.2f}" if prices else "—",
                  "Stock": f"{stock}/{len(variations)} variations available"}
        for name, value in values.items():
            self.info_labels[name].configure(text=value)
        self._render_variations()
        self._update_summary()

    def _product_failed(self, message):
        self.load_button.configure(state="normal")
        self.status_label.configure(text="Product loading failed.", text_color=colors.DANGER)
        self._set_error(message)

    def _render_variations(self):
        for child in self.variation_content.winfo_children(): child.destroy()
        variations = self.product.available_variations
        if not variations:
            ctk.CTkLabel(self.variation_content, text="This product has no purchasable variations.", font=fonts.SMALL, text_color=colors.WARNING).pack(anchor="w")
            return
        keys = list(dict.fromkeys(key for variation in variations for key in variation.options))
        if not keys:
            self.selected_variation = variations[0]
            ctk.CTkLabel(self.variation_content, text=f"SKU: {self.selected_variation.name or 'Default variation'}", font=fonts.SMALL).pack(anchor="w")
            return
        self.option_vars = {}
        for key in keys:
            values = list(dict.fromkeys(v.options.get(key, "") for v in variations if key in v.options))
            frame = ctk.CTkFrame(self.variation_content, fg_color=colors.SURFACE, corner_radius=6)
            frame.pack(fill="x", pady=4)
            ctk.CTkLabel(frame, text=key, font=fonts.SMALL_BOLD).pack(anchor="w", padx=10, pady=(7, 2))
            var = ctk.StringVar(value=values[0])
            self.option_vars[key] = var
            buttons = ctk.CTkFrame(frame, fg_color="transparent")
            buttons.pack(fill="x", padx=7, pady=(0, 7))
            for value in values:
                ctk.CTkRadioButton(buttons, text=value, variable=var, value=value, font=fonts.SMALL,
                                   command=self._selection_changed).pack(side="left", padx=4)
        self._selection_changed()

    def _selection_changed(self):
        selected = {key: var.get() for key, var in self.option_vars.items()}
        self.selected_variation = next((v for v in self.product.available_variations if v.options == selected), None)
        self._set_error("" if self.selected_variation else "That combination is unavailable.")
        self._update_summary()

    def _change_quantity(self, change):
        self.quantity = max(1, self.quantity + change)
        self.quantity_label.configure(text=str(self.quantity))
        self._update_summary()

    def _trigger_changed(self):
        needs_price = self.trigger_var.get() in (TriggerCondition.PRICE_TARGET.value, TriggerCondition.PRICE_AND_STOCK.value)
        self.target_entry.configure(state="normal" if needs_price else "disabled")
        self._update_summary()

    def _profile(self):
        if self.product is None: raise ValueError("Load a product before saving the profile.")
        if self.selected_variation is None: raise ValueError("Select an available variation before saving.")
        trigger = TriggerCondition(self.trigger_var.get())
        raw_price = self.target_entry.get().replace("₱", "").replace(",", "").strip()
        target_price = None
        if trigger in (TriggerCondition.PRICE_TARGET, TriggerCondition.PRICE_AND_STOCK):
            try: target_price = float(raw_price)
            except ValueError: raise ValueError("Enter a valid target price.")
            if target_price <= 0: raise ValueError("Target price must be greater than zero.")
        interval = int(self.polling_menu.get().split()[0])
        profile = PurchaseProfile(profile_name=self.product.product_name, product=self.product,
                                  selected_variations=[self.selected_variation], quantity=self.quantity,
                                  trigger=trigger, target_price=target_price, polling_interval=interval,
                                  auto_checkout=bool(self.auto_checkout_var.get()), lock_selected_variations=bool(self.lock_var.get()))
        PurchaseProfileService.validate(profile)
        return profile

    def _save(self):
        try:
            profile = self._profile()
            self.save_button.configure(state="disabled", text="Starting…")
            threading.Thread(target=self._save_worker, args=(profile,), daemon=True).start()
        except ValueError as exc:
            self._set_error(str(exc))

    def _save_worker(self, profile):
        try:
            self.on_save(profile)
            self.after(0, self.destroy)
        except Exception as exc:
            self.after(0, lambda: self._save_failed(str(exc)))

    def _save_failed(self, message):
        self.save_button.configure(state="normal", text="Save Purchase Profile")
        self._set_error(message)

    def _update_summary(self):
        product = self.product.product_name if self.product else "—"
        shop = self.product.shop_name if self.product else "—"
        variation = self.selected_variation.name if self.selected_variation else "—"
        price = self.target_entry.get().strip() or "—"
        trigger = next((text for value, text in [(TriggerCondition.TRACK_ONLY.value, "Track Only"), (TriggerCondition.PRICE_TARGET.value, "Price ≤ Target"), (TriggerCondition.STOCK_AVAILABLE.value, "Stock Available"), (TriggerCondition.PRICE_AND_STOCK.value, "Price AND Stock")] if value == self.trigger_var.get()), "—")
        self.summary_label.configure(text=f"Product    {product}\nShop       {shop}\nVariation  {variation}\nQuantity   {self.quantity}\nTrigger    {trigger}\nTarget     {('₱' + price) if price else '—'}\nPolling    {self.polling_menu.get()}\nCheckout   {'Enabled' if self.auto_checkout_var.get() else 'Disabled'}")

    def _set_error(self, message):
        self.error_label.configure(text=message)
