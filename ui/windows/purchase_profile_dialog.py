"""Purchase Profile dialog for creating a real V2 purchase profile."""

import threading

import customtkinter as ctk

from purchase.models.purchase_profile import PurchaseProfile
from purchase.models.trigger_condition import TriggerCondition
from purchase.services.product_loader import ProductLoader
from purchase.parser.url_parser import URLParser
from purchase.services.purchase_profile_service import PurchaseProfileService
from ui import colors, fonts, icons


class PurchaseProfileDialog(ctk.CTkToplevel):
    """Visual presentation for the existing Purchase Profile workflow."""

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
        self.geometry("780x1000")
        self.minsize(720, 700)
        self.configure(fg_color=colors.BACKGROUND)
        self.transient(master)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        self._build_ui()
        self._update_summary()

    def _build_ui(self):
        header = ctk.CTkFrame(
            self,
            fg_color=colors.TOPBAR,
            border_width=1,
            border_color=colors.BORDER,
            corner_radius=0,
            height=76,
        )
        header.pack(fill="x", side="top")
        header.pack_propagate(False)
        header.grid_columnconfigure(1, weight=1)

        icon_image = icons.load_icon(icons.PURCHASE_PROFILE, colors.PRIMARY_HOVER, (32, 32))
        ctk.CTkLabel(
            header,
            text="",
            image=icon_image,
            width=42,
            height=42,
            fg_color=colors.PRIMARY_SOFT,
            corner_radius=9,
        ).grid(row=0, column=0, rowspan=2, padx=(18, 11), pady=15)

        ctk.CTkLabel(
            header,
            text="Purchase Profile",
            font=fonts.SUBTITLE,
            text_color=colors.TEXT_PRIMARY,
            anchor="w",
        ).grid(row=0, column=1, sticky="sw", pady=(11, 0))

        ctk.CTkLabel(
            header,
            text="Create a monitoring profile for a Shopee product",
            font=fonts.SMALL,
            text_color=colors.TEXT_SECONDARY,
            anchor="w",
        ).grid(row=1, column=1, sticky="nw", pady=(0, 11))

        ctk.CTkButton(
            header,
            text="×",
            width=38,
            height=38,
            fg_color="transparent",
            hover_color=colors.CARD_HOVER,
            text_color=colors.TEXT_SECONDARY,
            font=fonts.HEADING,
            command=self.destroy,
        ).grid(row=0, column=2, rowspan=2, padx=(8, 15), pady=18)

        footer = ctk.CTkFrame(
            self,
            fg_color=colors.TOPBAR,
            border_width=1,
            border_color=colors.BORDER,
            corner_radius=0,
            height=72,
        )
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)

        self.error_label = ctk.CTkLabel(
            footer,
            text="",
            font=fonts.SMALL,
            text_color=colors.DANGER,
            anchor="w",
            justify="left",
        )
        self.error_label.pack(side="left", fill="x", expand=True, padx=(18, 10), pady=10)

        ctk.CTkButton(
            footer,
            text="Cancel",
            width=96,
            height=38,
            fg_color=colors.SURFACE_LIGHT,
            hover_color=colors.CARD_HOVER,
            text_color=colors.TEXT_PRIMARY,
            font=fonts.BUTTON,
            command=self.destroy,
        ).pack(side="right", padx=(8, 15), pady=17)

        self.save_button = ctk.CTkButton(
            footer,
            text="Save Purchase Profile",
            width=190,
            height=38,
            fg_color=colors.PRIMARY,
            hover_color=colors.PRIMARY_HOVER,
            text_color=colors.BUTTON_TEXT,
            font=fonts.BUTTON,
            command=self._save,
        )
        self.save_button.pack(side="right", pady=17)

        self.scroll = ctk.CTkScrollableFrame(
            self,
            fg_color=colors.BACKGROUND,
            corner_radius=0,
            scrollbar_button_color=colors.SURFACE_LIGHT,
            scrollbar_button_hover_color=colors.CARD_HOVER,
        )
        self.scroll.pack(fill="both", expand=True, padx=14, pady=12)
        self.scroll.grid_columnconfigure(0, weight=3, uniform="purchase_columns")
        self.scroll.grid_columnconfigure(1, weight=2, uniform="purchase_columns")

        self.source_card = self._card(self.scroll, "1", "Product Source", "Load a Shopee product through Chrome")
        self.source_card.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=(0, 10))

        self.info_card = self._card(self.scroll, "2", "Product Information", "Read only")
        self.info_card.grid(row=0, column=1, sticky="nsew", padx=(6, 0), pady=(0, 10))

        self.variation_card = self._card(self.scroll, "3", "Product Variations", "Select one available SKU")
        self.variation_card.grid(row=1, column=0, sticky="nsew", padx=(0, 6), pady=(0, 10))

        self.settings_card = self._card(self.scroll, "4", "Purchase Settings", "Monitoring and purchase rules")
        self.settings_card.grid(row=1, column=1, sticky="nsew", padx=(6, 0), pady=(0, 10))

        self.checkout_card = self._card(self.scroll, "5", "Auto Checkout", "Uses configured cart, payment, shipping, and OTP")
        self.checkout_card.grid(row=2, column=0, sticky="nsew", padx=(0, 6), pady=(0, 4))

        self.summary_card = self._card(self.scroll, "6", "Purchase Summary", "Updates as you configure the profile")
        self.summary_card.grid(row=2, column=1, sticky="nsew", padx=(6, 0), pady=(0, 4))

        self._build_source()
        self._build_info()
        self._build_variations()
        self._build_settings()
        self._build_checkout()
        self._build_summary()

    def _card(self, parent, step, title, subtitle):
        card = ctk.CTkFrame(
            parent,
            fg_color=colors.CARD,
            border_width=1,
            border_color=colors.BORDER,
            corner_radius=10,
        )
        title_row = ctk.CTkFrame(card, fg_color="transparent", height=28)
        title_row.pack(fill="x", padx=14, pady=(12, 0))
        title_row.pack_propagate(False)

        ctk.CTkLabel(
            title_row,
            text=step,
            width=22,
            height=22,
            corner_radius=11,
            fg_color=colors.PRIMARY,
            text_color=colors.BUTTON_TEXT,
            font=fonts.SMALL_BOLD,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(
            title_row,
            text=title,
            font=fonts.BODY,
            text_color=colors.TEXT_PRIMARY,
            anchor="w",
        ).pack(side="left")
        ctk.CTkLabel(
            card,
            text=subtitle,
            font=fonts.SMALL,
            text_color=colors.TEXT_SECONDARY,
            anchor="w",
        ).pack(fill="x", padx=14, pady=(1, 9))
        return card

    def _build_source(self):
        row = ctk.CTkFrame(self.source_card, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=(1, 0))
        row.grid_columnconfigure(0, weight=1)

        self.url_entry = ctk.CTkEntry(
            row,
            placeholder_text="https://shopee.ph/...",
            height=38,
            fg_color=colors.INPUT,
            border_color=colors.INPUT_BORDER,
            border_width=1,
            text_color=colors.TEXT_PRIMARY,
            placeholder_text_color=colors.TEXT_MUTED,
            font=fonts.SMALL,
        )
        self.url_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        self.load_button = ctk.CTkButton(
            row,
            text="▶  Load Product",
            width=122,
            height=38,
            fg_color=colors.PRIMARY,
            hover_color=colors.PRIMARY_HOVER,
            text_color=colors.BUTTON_TEXT,
            font=fonts.SMALL_BOLD,
            command=self._load_product,
        )
        self.load_button.grid(row=0, column=1)

        self.status_label = ctk.CTkLabel(
            self.source_card,
            text="Ready to load a product.",
            font=fonts.SMALL,
            text_color=colors.TEXT_SECONDARY,
            justify="left",
            anchor="w",
            wraplength=360,
        )
        self.status_label.pack(fill="x", padx=14, pady=(9, 13))

    def _build_info(self):
        self.info_labels = {}
        info_body = ctk.CTkFrame(self.info_card, fg_color="transparent")
        info_body.pack(fill="x", padx=14, pady=(0, 10))
        info_body.grid_columnconfigure(1, weight=1)

        labels = ("Product Name", "Shop", "Product ID", "Current Price", "Stock")
        for row_index, label in enumerate(labels):
            ctk.CTkLabel(
                info_body,
                text=label,
                font=fonts.SMALL,
                text_color=colors.TEXT_SECONDARY,
                anchor="w",
            ).grid(row=row_index, column=0, sticky="w", pady=5)
            value = ctk.CTkLabel(
                info_body,
                text="—",
                font=fonts.SMALL,
                text_color=colors.TEXT_PRIMARY,
                anchor="e",
                justify="right",
                wraplength=205,
            )
            value.grid(row=row_index, column=1, sticky="e", pady=5, padx=(12, 0))
            self.info_labels[label] = value
            if row_index < len(labels) - 1:
                ctk.CTkFrame(info_body, height=1, fg_color=colors.DIVIDER).grid(
                    row=row_index, column=0, columnspan=2, sticky="ew", pady=(31, 0)
                )

    def _build_variations(self):
        self.variation_content = ctk.CTkFrame(self.variation_card, fg_color="transparent")
        self.variation_content.pack(fill="both", expand=True, padx=14, pady=(0, 13))
        self.variation_hint = ctk.CTkLabel(
            self.variation_content,
            text="Load a product to see its available variations.",
            font=fonts.SMALL,
            text_color=colors.TEXT_SECONDARY,
            justify="left",
            anchor="w",
            wraplength=380,
        )
        self.variation_hint.pack(fill="x")

    def _build_settings(self):
        quantity = ctk.CTkFrame(self.settings_card, fg_color="transparent")
        quantity.pack(fill="x", padx=14, pady=(0, 1))
        quantity.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(quantity, text="Quantity", font=fonts.SMALL, text_color=colors.TEXT_PRIMARY, anchor="w").grid(
            row=0, column=0, sticky="w"
        )

        controls = ctk.CTkFrame(quantity, fg_color=colors.INPUT, border_width=1, border_color=colors.BORDER, corner_radius=7)
        controls.grid(row=0, column=1, sticky="e")
        ctk.CTkButton(controls, text="−", width=34, height=32, fg_color="transparent", hover_color=colors.CARD_HOVER,
                      font=fonts.BODY, command=lambda: self._change_quantity(-1)).pack(side="left")
        self.quantity_label = ctk.CTkLabel(controls, text="1", width=34, font=fonts.BODY, text_color=colors.TEXT_PRIMARY)
        self.quantity_label.pack(side="left")
        ctk.CTkButton(controls, text="+", width=34, height=32, fg_color="transparent", hover_color=colors.CARD_HOVER,
                      font=fonts.BODY, command=lambda: self._change_quantity(1)).pack(side="left")

        ctk.CTkLabel(self.settings_card, text="Trigger (Monitoring Condition)", font=fonts.SMALL,
                     text_color=colors.TEXT_PRIMARY, anchor="w").pack(fill="x", padx=14, pady=(12, 4))
        labels = [
            (TriggerCondition.TRACK_ONLY, "Track Only"),
            (TriggerCondition.PRICE_TARGET, "Price ≤ Target"),
            (TriggerCondition.STOCK_AVAILABLE, "Stock Available"),
            (TriggerCondition.PRICE_AND_STOCK, "Both Price AND Stock"),
        ]
        for value, text in labels:
            ctk.CTkRadioButton(
                self.settings_card, text=text, variable=self.trigger_var, value=value.value, font=fonts.SMALL,
                text_color=colors.TEXT_PRIMARY, fg_color=colors.PRIMARY, hover_color=colors.PRIMARY_HOVER,
                border_color=colors.BORDER_STRONG, command=self._trigger_changed,
            ).pack(anchor="w", padx=14, pady=2)

        target_row = ctk.CTkFrame(self.settings_card, fg_color="transparent")
        target_row.pack(fill="x", padx=14, pady=(10, 4))
        target_row.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(target_row, text="Target Price", font=fonts.SMALL, text_color=colors.TEXT_SECONDARY).grid(
            row=0, column=0, sticky="w"
        )
        self.target_entry = ctk.CTkEntry(
            target_row, placeholder_text="₱0.00", height=36, width=170, fg_color=colors.INPUT,
            border_color=colors.INPUT_BORDER, border_width=1, text_color=colors.TEXT_PRIMARY,
            placeholder_text_color=colors.TEXT_MUTED, font=fonts.SMALL,
        )
        self.target_entry.grid(row=0, column=1, sticky="e")
        self.target_entry.bind("<KeyRelease>", lambda _event: self._update_summary())

        polling_row = ctk.CTkFrame(self.settings_card, fg_color="transparent")
        polling_row.pack(fill="x", padx=14, pady=4)
        polling_row.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(polling_row, text="Polling Interval", font=fonts.SMALL, text_color=colors.TEXT_SECONDARY).grid(
            row=0, column=0, sticky="w"
        )
        self.polling_menu = ctk.CTkOptionMenu(
            polling_row, values=["5 seconds", "10 seconds", "30 seconds", "60 seconds"], width=170, height=36,
            fg_color=colors.INPUT, button_color=colors.PRIMARY, button_hover_color=colors.PRIMARY_HOVER,
            dropdown_fg_color=colors.CARD, dropdown_hover_color=colors.CARD_HOVER, font=fonts.SMALL,
            command=lambda _value: self._update_summary(),
        )
        self.polling_menu.set("30 seconds")
        self.polling_menu.grid(row=0, column=1, sticky="e")

        self.lock_switch = ctk.CTkCheckBox(
            self.settings_card, text="Lock selected variations", variable=self.lock_var, font=fonts.SMALL,
            text_color=colors.TEXT_PRIMARY, fg_color=colors.PRIMARY, hover_color=colors.PRIMARY_HOVER,
            border_color=colors.BORDER_STRONG, command=self._update_summary,
        )
        self.lock_switch.select()
        self.lock_switch.pack(anchor="w", padx=14, pady=(7, 13))

    def _build_checkout(self):
        row = ctk.CTkFrame(self.checkout_card, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=(0, 7))
        row.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(row, text="Enable Auto Checkout", font=fonts.BODY, text_color=colors.TEXT_PRIMARY, anchor="w").grid(
            row=0, column=0, sticky="w"
        )
        self.auto_switch = ctk.CTkSwitch(
            row, text="", width=44, height=24, variable=self.auto_checkout_var,
            progress_color=colors.PRIMARY, button_color=colors.TEXT_PRIMARY, button_hover_color=colors.TEXT_PRIMARY,
            command=self._update_summary,
        )
        self.auto_switch.grid(row=0, column=1, sticky="e")
        ctk.CTkLabel(
            self.checkout_card,
            text="When enabled, the existing purchase pipeline prepares cart and verifies checkout. Global Armed Mode remains the final safety gate.",
            font=fonts.SMALL, text_color=colors.TEXT_SECONDARY, justify="left", anchor="w", wraplength=350,
        ).pack(fill="x", padx=14, pady=(0, 10))

    def _build_summary(self):
        summary = ctk.CTkFrame(self.summary_card, fg_color="transparent")
        summary.pack(fill="x", padx=14, pady=(0, 11))
        summary.grid_columnconfigure(1, weight=1)
        summary.grid_columnconfigure(3, weight=1)
        self.summary_fields = {}
        fields = [
            ("Product", "product"), ("Shop", "shop"), ("Variation", "variation"), ("Quantity", "quantity"),
            ("Trigger", "trigger"), ("Target Price", "target"), ("Polling", "polling"), ("Checkout", "checkout"),
        ]
        for index, (label, key) in enumerate(fields):
            row = index % 4
            col = 0 if index < 4 else 2
            value_col = col + 1
            ctk.CTkLabel(summary, text=label, font=fonts.SMALL, text_color=colors.TEXT_SECONDARY, anchor="w").grid(
                row=row, column=col, sticky="w", pady=4
            )
            value = ctk.CTkLabel(
                summary, text="—", font=fonts.SMALL, text_color=colors.TEXT_PRIMARY, anchor="e", justify="right", wraplength=145,
            )
            value.grid(row=row, column=value_col, sticky="e", padx=(8, 0), pady=4)
            self.summary_fields[key] = value

    def _load_product(self):
        url = self.url_entry.get().strip()
        try:
            reference = URLParser.parse(url)
        except ValueError as exc:
            self._set_error(str(exc))
            return
        self._set_error("")
        self.load_button.configure(state="disabled")
        self.status_label.configure(
            text="Opening Chrome\nReading Product\nFetching browser API…", text_color=colors.INFO,
        )
        threading.Thread(target=self._load_worker, args=(reference,), daemon=True).start()

    def _load_worker(self, reference):
        try:
            product = ProductLoader().load(reference)
            if product is None:
                raise RuntimeError("Shopee returned no product information.")
            # The browser-loaded response can expose a canonical share URL;
            # retain the user-entered PDP URL for the purchase flow.
            product.product_url = reference.url
            self.after(0, lambda: self._product_loaded(product))
        except Exception as exc:
            error_message = str(exc)

            self.after(
                0,
                lambda message=error_message: self._load_failed(message)
            )

    def _product_loaded(self, product):
        self.product = product
        self.load_button.configure(state="normal")
        self.status_label.configure(text="✓ Product Loaded\nParsing Variations complete.", text_color=colors.SUCCESS)
        variations = product.available_variations
        prices = [v.price for v in variations if v.price is not None]
        stock = sum(1 for v in variations if v.has_stock)
        values = {
            "Product Name": product.product_name,
            "Shop": product.shop_name or "—",
            "Product ID": str(product.item_id),
            "Current Price": f"₱{min(prices):,.2f}" if prices else "—",
            "Stock": f"{stock}/{len(variations)} variations available",
        }
        for name, value in values.items():
            self.info_labels[name].configure(text=value)
        self._render_variations()
        self._update_summary()

    def _product_failed(self, message):
        self.load_button.configure(state="normal")
        self.status_label.configure(text="Product loading failed.", text_color=colors.DANGER)
        self._set_error(message)

    def _render_variations(self):
        for child in self.variation_content.winfo_children():
            child.destroy()
        variations = self.product.available_variations
        if not variations:
            ctk.CTkLabel(
                self.variation_content, text="This product has no purchasable variations.", font=fonts.SMALL,
                text_color=colors.WARNING, anchor="w",
            ).pack(fill="x")
            return
        keys = list(dict.fromkeys(key for variation in variations for key in variation.options))
        if not keys:
            self.selected_variation = variations[0]
            ctk.CTkLabel(
                self.variation_content,
                text=f"SKU: {self.selected_variation.name or 'Default variation'}",
                font=fonts.SMALL, text_color=colors.TEXT_PRIMARY, anchor="w",
            ).pack(fill="x")
            return
        self.option_vars = {}
        for key in keys:
            values = list(dict.fromkeys(v.options.get(key, "") for v in variations if key in v.options))
            frame = ctk.CTkFrame(
                self.variation_content, fg_color=colors.SURFACE, border_width=1,
                border_color=colors.BORDER, corner_radius=7,
            )
            frame.pack(fill="x", pady=4)
            ctk.CTkLabel(
                frame, text=key, font=fonts.SMALL_BOLD, text_color=colors.TEXT_PRIMARY, anchor="w",
            ).pack(fill="x", padx=10, pady=(8, 3))
            var = ctk.StringVar(value=values[0])
            self.option_vars[key] = var
            buttons = ctk.CTkFrame(frame, fg_color="transparent")
            buttons.pack(fill="x", padx=8, pady=(0, 8))
            self._add_wrapped_variation_buttons(buttons, values, var)
        self._selection_changed()

    def _add_wrapped_variation_buttons(self, parent, values, variable):
        """Lay out dynamic variation radios in rows without horizontal overflow."""
        max_width = 355
        current_width = 0
        row = 0
        column = 0
        for value in values:
            estimated = max(82, min(190, 42 + len(str(value)) * 7))
            if column > 0 and current_width + estimated > max_width:
                row += 1
                column = 0
                current_width = 0
            radio = ctk.CTkRadioButton(
                parent, text=str(value), variable=variable, value=value, font=fonts.SMALL,
                text_color=colors.TEXT_PRIMARY, fg_color=colors.PRIMARY, hover_color=colors.PRIMARY_HOVER,
                border_color=colors.BORDER_STRONG, command=self._selection_changed,
            )
            radio.grid(row=row, column=column, sticky="w", padx=(3, 10), pady=3)
            column += 1
            current_width += estimated

    def _selection_changed(self):
        selected = {key: var.get() for key, var in self.option_vars.items()}
        self.selected_variation = next(
            (variation for variation in self.product.available_variations if variation.options == selected),
            None,
        )
        self._set_error("" if self.selected_variation else "That combination is unavailable.")
        self._update_summary()

    def _change_quantity(self, change):
        self.quantity = max(1, self.quantity + change)
        self.quantity_label.configure(text=str(self.quantity))
        self._update_summary()

    def _trigger_changed(self):
        needs_price = self.trigger_var.get() in (
            TriggerCondition.PRICE_TARGET.value,
            TriggerCondition.PRICE_AND_STOCK.value,
        )
        self.target_entry.configure(state="normal" if needs_price else "disabled")
        self._update_summary()

    def _profile(self):
        if self.product is None:
            raise ValueError("Load a product before saving the profile.")
        if self.selected_variation is None:
            raise ValueError("Select an available variation before saving.")
        trigger = TriggerCondition(self.trigger_var.get())
        raw_price = self.target_entry.get().replace("₱", "").replace(",", "").strip()
        target_price = None
        if trigger in (TriggerCondition.PRICE_TARGET, TriggerCondition.PRICE_AND_STOCK):
            try:
                target_price = float(raw_price)
            except ValueError:
                raise ValueError("Enter a valid target price.")
            if target_price <= 0:
                raise ValueError("Target price must be greater than zero.")
        interval = int(self.polling_menu.get().split()[0])
        profile = PurchaseProfile(
            profile_name=self.product.product_name,
            product=self.product,
            selected_variations=[self.selected_variation],
            quantity=self.quantity,
            trigger=trigger,
            target_price=target_price,
            polling_interval=interval,
            auto_checkout=bool(self.auto_checkout_var.get()),
            lock_selected_variations=bool(self.lock_var.get()),
        )
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
            error_message = str(exc)

            self.after(
                0,
                lambda message=error_message: self._save_failed(message)
            )

    def _save_failed(self, message):
        self.save_button.configure(state="normal", text="Save Purchase Profile")
        self._set_error(message)

    def _update_summary(self):
        product = self.product.product_name if self.product else "—"
        shop = self.product.shop_name if self.product else "—"
        variation = self.selected_variation.name if self.selected_variation else "—"
        price = self.target_entry.get().strip() or "—"
        trigger = next(
            (
                text
                for value, text in [
                    (TriggerCondition.TRACK_ONLY.value, "Track Only"),
                    (TriggerCondition.PRICE_TARGET.value, "Price ≤ Target"),
                    (TriggerCondition.STOCK_AVAILABLE.value, "Stock Available"),
                    (TriggerCondition.PRICE_AND_STOCK.value, "Price AND Stock"),
                ]
                if value == self.trigger_var.get()
            ),
            "—",
        )
        values = {
            "product": product,
            "shop": shop,
            "variation": variation,
            "quantity": str(self.quantity),
            "trigger": trigger,
            "target": f"₱{price}" if price != "—" else "—",
            "polling": self.polling_menu.get(),
            "checkout": "Enabled" if self.auto_checkout_var.get() else "Disabled",
        }
        if hasattr(self, "summary_fields"):
            for key, value in values.items():
                self.summary_fields[key].configure(
                    text=value,
                    text_color=(
                        colors.SUCCESS
                        if key == "checkout" and self.auto_checkout_var.get()
                        else colors.TEXT_PRIMARY
                    ),
                )

    def _set_error(self, message):
        self.error_label.configure(text=message)
