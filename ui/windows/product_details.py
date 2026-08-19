import customtkinter as ctk

from ui import colors, fonts


class ProductDetailsWindow(ctk.CTkToplevel):

    def __init__(self, parent, product):
        super().__init__(parent)

        self.product = product

        self.title("Product Details")
        self.geometry("760x680")
        self.minsize(760, 680)
        self.resizable(False, False)

        self.configure(
            fg_color=colors.BACKGROUND
        )

        self.build_ui()

        # Keep the details window above the main application.
        self.transient(parent)
        self.grab_set()

    # =====================================================
    # Main UI
    # =====================================================

    def build_ui(self):

        outer = ctk.CTkFrame(
            self,
            fg_color="transparent"
        )

        outer.pack(
            fill="both",
            expand=True,
            padx=24,
            pady=24
        )

        # =================================================
        # Header Card
        # =================================================

        header = ctk.CTkFrame(
            outer,
            fg_color=colors.CARD,
            border_width=1,
            border_color=colors.BORDER,
            corner_radius=10
        )

        header.pack(
            fill="x",
            pady=(0, 12)
        )

        header_content = ctk.CTkFrame(
            header,
            fg_color="transparent"
        )

        header_content.pack(
            fill="x",
            padx=20,
            pady=18
        )

        # Thumbnail

        thumbnail = ctk.CTkFrame(
            header_content,
            width=72,
            height=72,
            fg_color=colors.SURFACE_LIGHT,
            border_width=1,
            border_color=colors.BORDER,
            corner_radius=10
        )

        thumbnail.pack(
            side="left"
        )

        thumbnail.pack_propagate(False)

        ctk.CTkLabel(
            thumbnail,
            text="📱",
            font=(fonts.FONT_FAMILY, 30)
        ).pack(
            expand=True
        )

        # Product information

        info = ctk.CTkFrame(
            header_content,
            fg_color="transparent"
        )

        info.pack(
            side="left",
            fill="x",
            expand=True,
            padx=(16, 0)
        )

        ctk.CTkLabel(
            info,
            text=self.product.name,
            font=fonts.SUBTITLE,
            text_color=colors.TEXT_PRIMARY,
            anchor="w",
            justify="left",
            wraplength=470
        ).pack(
            anchor="w"
        )

        ctk.CTkLabel(
            info,
            text="Shopee • Currently Monitored",
            font=fonts.SMALL,
            text_color=colors.TEXT_SECONDARY
        ).pack(
            anchor="w",
            pady=(5, 0)
        )

        # Status

        stock_text, stock_bg, stock_color = self.stock_badge_style(
            getattr(self.product, "stock", "")
        )

        ctk.CTkLabel(
            header_content,
            text=stock_text,
            width=100,
            height=30,
            corner_radius=15,
            fg_color=stock_bg,
            text_color=stock_color,
            font=fonts.BADGE
        ).pack(
            side="right",
            anchor="n"
        )

        # =================================================
        # Pricing Card
        # =================================================

        pricing = ctk.CTkFrame(
            outer,
            fg_color=colors.CARD,
            border_width=1,
            border_color=colors.BORDER,
            corner_radius=10
        )

        pricing.pack(
            fill="x",
            pady=(0, 12)
        )

        self.section_header(
            pricing,
            "Pricing"
        )

        pricing_body = ctk.CTkFrame(
            pricing,
            fg_color="transparent"
        )

        pricing_body.pack(
            fill="x",
            padx=20,
            pady=(0, 18)
        )

        # Current price

        current = ctk.CTkFrame(
            pricing_body,
            fg_color=colors.SURFACE,
            corner_radius=8
        )

        current.pack(
            side="left",
            fill="x",
            expand=True,
            padx=(0, 6)
        )

        ctk.CTkLabel(
            current,
            text="Current Price",
            font=fonts.SMALL,
            text_color=colors.TEXT_SECONDARY
        ).pack(
            anchor="w",
            padx=14,
            pady=(12, 2)
        )

        price_row = ctk.CTkFrame(
            current,
            fg_color="transparent"
        )

        price_row.pack(
            anchor="w",
            padx=14,
            pady=(0, 12)
        )

        ctk.CTkLabel(
            price_row,
            text=self.value("current_price"),
            font=(fonts.FONT_FAMILY, 24, "bold"),
            text_color=colors.TEXT_PRIMARY
        ).pack(
            side="left"
        )

        discount = getattr(
            self.product,
            "discount",
            "--"
        )

        discount_bg, discount_color = self.discount_badge_style(
            discount
        )

        ctk.CTkLabel(
            price_row,
            text=str(discount),
            width=48,
            height=22,
            corner_radius=11,
            fg_color=discount_bg,
            text_color=discount_color,
            font=fonts.SMALL_BOLD
        ).pack(
            side="left",
            padx=(8, 0)
        )

        # Original price

        original = ctk.CTkFrame(
            pricing_body,
            fg_color=colors.SURFACE,
            corner_radius=8
        )

        original.pack(
            side="left",
            fill="x",
            expand=True,
            padx=6
        )

        ctk.CTkLabel(
            original,
            text="Original Price",
            font=fonts.SMALL,
            text_color=colors.TEXT_SECONDARY
        ).pack(
            anchor="w",
            padx=14,
            pady=(12, 2)
        )

        ctk.CTkLabel(
            original,
            text=self.value("original_price"),
            font=fonts.SUBTITLE,
            text_color=colors.TEXT_PRIMARY
        ).pack(
            anchor="w",
            padx=14,
            pady=(0, 12)
        )

        # Target price

        target = ctk.CTkFrame(
            pricing_body,
            fg_color=colors.SURFACE,
            corner_radius=8
        )

        target.pack(
            side="left",
            fill="x",
            expand=True,
            padx=(6, 0)
        )

        ctk.CTkLabel(
            target,
            text="Target Price",
            font=fonts.SMALL,
            text_color=colors.TEXT_SECONDARY
        ).pack(
            anchor="w",
            padx=14,
            pady=(12, 2)
        )

        target_price = getattr(
            self.product,
            "target_price",
            None
        )

        target_text = (
            f"₱{target_price:,.2f}"
            if isinstance(target_price, (int, float))
            else "--"
        )

        ctk.CTkLabel(
            target,
            text=target_text,
            font=fonts.SUBTITLE,
            text_color=colors.SUCCESS
            if target_price
            else colors.TEXT_MUTED
        ).pack(
            anchor="w",
            padx=14,
            pady=(0, 12)
        )

        # =================================================
        # Monitoring Card
        # =================================================

        monitoring = ctk.CTkFrame(
            outer,
            fg_color=colors.CARD,
            border_width=1,
            border_color=colors.BORDER,
            corner_radius=10
        )

        monitoring.pack(
            fill="x",
            pady=(0, 12)
        )

        self.section_header(
            monitoring,
            "Monitoring"
        )

        monitoring_body = ctk.CTkFrame(
            monitoring,
            fg_color="transparent"
        )

        monitoring_body.pack(
            fill="x",
            padx=20,
            pady=(0, 16)
        )

        self.info_row(
            monitoring_body,
            "Auto Checkout",
            "ENABLED"
            if getattr(self.product, "auto_checkout", False)
            else "DISABLED",
            value_color=(
                colors.SUCCESS
                if getattr(self.product, "auto_checkout", False)
                else colors.TEXT_MUTED
            )
        )

        self.info_row(
            monitoring_body,
            "Target Locked",
            "LOCKED"
            if getattr(self.product, "target_locked", False)
            else "UNLOCKED",
            value_color=(
                colors.SUCCESS
                if getattr(self.product, "target_locked", False)
                else colors.TEXT_MUTED
            )
        )

        self.info_row(
            monitoring_body,
            "Last Checked",
            "Just now"
        )

        # =================================================
        # Technical Information
        # =================================================

        technical = ctk.CTkFrame(
            outer,
            fg_color=colors.CARD,
            border_width=1,
            border_color=colors.BORDER,
            corner_radius=10
        )

        technical.pack(
            fill="x",
            pady=(0, 12)
        )

        self.section_header(
            technical,
            "Technical Information"
        )

        technical_body = ctk.CTkFrame(
            technical,
            fg_color="transparent"
        )

        technical_body.pack(
            fill="x",
            padx=20,
            pady=(0, 16)
        )

        self.info_row(
            technical_body,
            "Shop ID",
            self.value("shop_id"),
            value_font=fonts.LOG
        )

        self.info_row(
            technical_body,
            "Item ID",
            self.value("item_id"),
            value_font=fonts.LOG
        )

        self.info_row(
            technical_body,
            "Model ID",
            self.value("model_id"),
            value_font=fonts.LOG
        )

        # =================================================
        # Footer
        # =================================================

        footer = ctk.CTkFrame(
            outer,
            fg_color="transparent"
        )

        footer.pack(
            fill="x"
        )

        ctk.CTkButton(
            footer,
            text="Close",
            width=110,
            height=36,
            fg_color=colors.PRIMARY,
            hover_color=colors.PRIMARY_HOVER,
            text_color=colors.TEXT_PRIMARY,
            font=fonts.BUTTON,
            command=self.destroy
        ).pack(
            side="right"
        )

    # =====================================================
    # UI Helpers
    # =====================================================

    def section_header(self, parent, text):

        ctk.CTkLabel(
            parent,
            text=text,
            font=fonts.HEADING,
            text_color=colors.TEXT_PRIMARY
        ).pack(
            anchor="w",
            padx=20,
            pady=(16, 10)
        )

    def info_row(
        self,
        parent,
        label,
        value,
        value_color=None,
        value_font=None
    ):

        row = ctk.CTkFrame(
            parent,
            fg_color="transparent"
        )

        row.pack(
            fill="x",
            pady=4
        )

        ctk.CTkLabel(
            row,
            text=label,
            font=fonts.BODY,
            text_color=colors.TEXT_SECONDARY
        ).pack(
            side="left"
        )

        ctk.CTkLabel(
            row,
            text=str(value),
            font=value_font or fonts.BODY,
            text_color=value_color or colors.TEXT_PRIMARY
        ).pack(
            side="right"
        )

    # =====================================================
    # Value / Style Helpers
    # =====================================================

    def value(self, field_name):

        value = getattr(
            self.product,
            field_name,
            ""
        )

        return str(value) if value else "--"

    def stock_badge_style(self, value):

        stock_value = str(value).upper()

        if stock_value == "IN STOCK":
            return (
                "IN STOCK",
                colors.SUCCESS_BG,
                colors.SUCCESS
            )

        if stock_value == "LOW STOCK":
            return (
                "LOW STOCK",
                colors.WARNING_BG,
                colors.WARNING
            )

        if stock_value == "OUT OF STOCK":
            return (
                "OUT OF STOCK",
                colors.DANGER_BG,
                colors.DANGER
            )

        return (
            stock_value or "--",
            colors.CARD_HOVER,
            colors.TEXT_SECONDARY
        )

    def discount_badge_style(self, discount):

        discount = str(discount)

        if discount.startswith("-"):
            return (
                colors.SUCCESS_BG,
                colors.SUCCESS
            )

        if discount.startswith("+"):
            return (
                colors.DANGER_BG,
                colors.DANGER
            )

        return (
            colors.CARD_HOVER,
            colors.TEXT_SECONDARY
        )