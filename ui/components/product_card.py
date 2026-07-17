import customtkinter as ctk

from ui import colors, fonts
from ui.windows.product_details import ProductDetailsWindow


class ProductCard(ctk.CTkFrame):

    def __init__(
        self,
        master,
        product,
        stop_callback=None
    ):
        super().__init__(
            master,
            fg_color=colors.CARD,
            border_color=colors.PRIMARY,
            border_width=1,
            corner_radius=8
        )

        self.product = product
        self.stop_callback = stop_callback

        self.metric_labels = {}
        self.stock_label = None

        self.grid_columnconfigure(1, weight=1)

        self.build_media()
        self.build_body()
        self.build_actions()

    def build_media(self):
        media_frame = ctk.CTkFrame(
            self,
            width=120,
            fg_color="transparent"
        )

        media_frame.grid(
            row=0,
            column=0,
            sticky="nsw",
            padx=(18, 16),
            pady=18
        )

        media_frame.grid_propagate(False)

        ctk.CTkLabel(
            media_frame,
            text="HOT",
            width=42,
            height=24,
            fg_color=colors.DANGER,
            corner_radius=6,
            font=("Segoe UI", 11, "bold"),
            text_color=colors.TEXT_PRIMARY
        ).pack(anchor="nw")

        self.product_image = ctk.CTkFrame(
            media_frame,
            width=82,
            height=100,
            fg_color=colors.SURFACE_LIGHT,
            border_width=1,
            border_color=colors.BORDER,
            corner_radius=8
        )

        self.product_image.pack(
            anchor="center",
            pady=(8, 0)
        )

        self.product_image.pack_propagate(False)

        ctk.CTkLabel(
            self.product_image,
            text="📱",
            font=("Segoe UI", 34),
            text_color=colors.TEXT_SECONDARY
        ).pack(expand=True)

    def build_body(self):
        self.body_frame = ctk.CTkFrame(
            self,
            fg_color="transparent"
        )

        self.body_frame.grid(
            row=0,
            column=1,
            sticky="nsew",
            pady=18
        )

        self.body_frame.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)

        self.name_label = ctk.CTkLabel(
            self.body_frame,
            text=self.product.name,
            font=fonts.HEADING,
            text_color=colors.TEXT_PRIMARY
        )

        self.name_label.grid(
            row=0,
            column=0,
            columnspan=5,
            sticky="w",
            pady=(0, 8)
        )

        self.add_metric(0, "Current Price", self.product.current_price, large=True)
        self.add_metric(1, "Original Price", self.product.original_price)
        self.add_metric(2, "Discount", self.product.discount, accent=self.discount_color())
        self.add_stock_metric(3, "Stock Status", self.product.stock)
        self.add_metric(4, "Last Checked", "Just now")

        self.build_auto_checkout()

    def build_actions(self):
        self.actions_frame = ctk.CTkFrame(
            self,
            width=160,
            fg_color="transparent"
        )

        self.actions_frame.grid(
            row=0,
            column=2,
            sticky="nse",
            padx=(18, 18),
            pady=18
        )

        self.actions_frame.grid_propagate(False)

        ctk.CTkButton(
            self.actions_frame,
            text="⋮",
            width=34,
            height=28,
            fg_color="transparent",
            hover_color=colors.CARD_HOVER,
            text_color=colors.TEXT_PRIMARY,
            command=lambda: None
        ).pack(anchor="e", pady=(0, 34))

        self.details_button = ctk.CTkButton(
            self.actions_frame,
            text="View Details",
            width=140,
            height=36,
            fg_color="transparent",
            border_width=1,
            border_color=colors.PRIMARY,
            hover_color=colors.PRIMARY_SOFT,
            text_color=colors.PRIMARY_HOVER,
            font=fonts.BUTTON,
            command=self.open_details
        )

        self.details_button.pack(anchor="e", pady=(0, 10))

        self.stop_button = ctk.CTkButton(
            self.actions_frame,
            text="⊘  Stop Monitoring",
            width=140,
            height=36,
            fg_color="transparent",
            border_width=1,
            border_color=colors.DANGER,
            hover_color=colors.DANGER_BG,
            text_color=colors.DANGER,
            font=fonts.BUTTON,
            command=self.stop_monitoring
        )

        self.stop_button.pack(anchor="e")

    def add_metric(self, column, label, value, large=False, accent=None):
        frame = ctk.CTkFrame(
            self.body_frame,
            fg_color="transparent"
        )

        frame.grid(
            row=1,
            column=column,
            sticky="nw",
            padx=(0, 24)
        )

        ctk.CTkLabel(
            frame,
            text=label,
            font=fonts.SMALL,
            text_color=colors.TEXT_SECONDARY
        ).pack(anchor="w")

        value_label = ctk.CTkLabel(
            frame,
            text=str(value) if value else "--",
            font=("Segoe UI", 22, "bold") if large else fonts.BODY,
            text_color=accent or colors.TEXT_PRIMARY
        )

        value_label.pack(
            anchor="w",
            pady=(2, 0)
        )

        self.metric_labels[label] = value_label

    def add_stock_metric(self, column, label, value):
        frame = ctk.CTkFrame(
            self.body_frame,
            fg_color="transparent"
        )

        frame.grid(
            row=1,
            column=column,
            sticky="nw",
            padx=(0, 24)
        )

        ctk.CTkLabel(
            frame,
            text=label,
            font=fonts.SMALL,
            text_color=colors.TEXT_SECONDARY
        ).pack(anchor="w")

        stock_text, badge_bg, badge_color = self.stock_badge_style(value)

        self.stock_label = ctk.CTkLabel(
            frame,
            text=stock_text,
            width=82,
            height=24,
            font=("Segoe UI", 11, "bold"),
            fg_color=badge_bg,
            text_color=badge_color,
            corner_radius=6
        )

        self.stock_label.pack(
            anchor="w",
            pady=(4, 0)
        )

    def build_auto_checkout(self):
        panel = ctk.CTkFrame(
            self.body_frame,
            fg_color=colors.SURFACE,
            border_width=1,
            border_color=colors.BORDER,
            corner_radius=8,
            height=56
        )

        panel.grid(
            row=2,
            column=0,
            columnspan=4,
            sticky="ew",
            pady=(16, 0),
            padx=(0, 24)
        )

        panel.grid_columnconfigure(1, weight=1)
        panel.grid_columnconfigure(3, weight=1)

        icon = ctk.CTkLabel(
            panel,
            text="▣",
            width=34,
            height=34,
            fg_color=colors.PRIMARY_SOFT,
            corner_radius=8,
            text_color=colors.PRIMARY_HOVER,
            font=fonts.HEADING
        )

        icon.grid(row=0, column=0, rowspan=2, padx=(12, 10), pady=10)

        ctk.CTkLabel(
            panel,
            text="Auto Checkout  ⓘ",
            font=("Segoe UI", 12, "bold"),
            text_color=colors.TEXT_PRIMARY
        ).grid(row=0, column=1, sticky="sw", pady=(8, 0))

        ctk.CTkLabel(
            panel,
            text="When Flash Sale or Promo hits",
            font=fonts.SMALL,
            text_color=colors.TEXT_SECONDARY
        ).grid(row=1, column=1, sticky="nw", pady=(0, 8))

        ctk.CTkLabel(
            panel,
            text="Status",
            font=fonts.SMALL,
            text_color=colors.TEXT_SECONDARY
        ).grid(row=0, column=2, sticky="sw", padx=(20, 10), pady=(8, 0))

        status_frame = ctk.CTkFrame(panel, fg_color="transparent")
        status_frame.grid(row=1, column=2, sticky="nw", padx=(20, 10), pady=(0, 8))

        ctk.CTkLabel(
            status_frame,
            text="ON",
            width=28,
            height=18,
            fg_color=colors.SUCCESS_BG,
            corner_radius=5,
            font=("Segoe UI", 10, "bold"),
            text_color=colors.SUCCESS
        ).pack(side="left", padx=(0, 8))

        ctk.CTkSwitch(
            status_frame,
            text="",
            width=42,
            command=lambda: None
        ).pack(side="left")

        ctk.CTkLabel(
            panel,
            text="Target",
            font=fonts.SMALL,
            text_color=colors.TEXT_SECONDARY
        ).grid(row=0, column=3, sticky="sw", padx=(20, 10), pady=(8, 0))

        ctk.CTkLabel(
            panel,
            text="Any Flash Sale  ✎",
            font=("Segoe UI", 12, "bold"),
            text_color=colors.TEXT_PRIMARY
        ).grid(row=1, column=3, sticky="nw", padx=(20, 10), pady=(0, 8))

    def discount_color(self):
        discount = str(self.product.discount)

        if discount.startswith("-"):
            return colors.SUCCESS

        if discount.startswith("+"):
            return colors.DANGER

        return colors.TEXT_PRIMARY

    def stock_badge_style(self, value):
        stock_value = str(value).upper()

        if stock_value == "IN STOCK":
            return "IN STOCK", colors.SUCCESS_BG, colors.SUCCESS

        if stock_value == "LOW STOCK":
            return "LOW STOCK", colors.WARNING_BG, colors.WARNING

        if stock_value == "OUT OF STOCK":
            return "OUT OF STOCK", colors.DANGER_BG, colors.DANGER

        return stock_value or "--", colors.CARD_HOVER, colors.TEXT_SECONDARY

    def update_data(self, product):

        self.product = product

        #
        # Product Name
        #
        self.name_label.configure(
            text=product.name
        )

        #
        # Current Price
        #
        self.metric_labels["Current Price"].configure(
            text=str(product.current_price)
        )

        #
        # Original Price
        #
        self.metric_labels["Original Price"].configure(
            text=str(product.original_price)
        )

        #
        # Discount
        #
        self.metric_labels["Discount"].configure(
            text=str(product.discount),
            text_color=self.discount_color()
        )

        #
        # Stock Badge
        #
        stock_text, badge_bg, badge_color = self.stock_badge_style(
            product.stock
        )

        self.stock_label.configure(
            text=stock_text,
            fg_color=badge_bg,
            text_color=badge_color
        )

        #
        # Last Checked
        #
        self.metric_labels["Last Checked"].configure(
            text="Just now"
        )

    def stop_monitoring(self):
        if self.stop_callback:
            self.stop_callback(self.product)

    def open_details(self):
        ProductDetailsWindow(
            self,
            self.product
        )
