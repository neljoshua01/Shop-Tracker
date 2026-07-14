import customtkinter as ctk

from ui import colors, fonts


class ProductDetailsWindow(ctk.CTkToplevel):

    def __init__(self, parent, product):
        super().__init__(parent)

        self.product = product

        self.title(product.name)
        self.geometry("700x650")
        self.resizable(False, False)
        self.configure(
            fg_color=colors.BACKGROUND
        )

        self.build_ui()

    def build_ui(self):
        container = ctk.CTkFrame(
            self,
            fg_color=colors.CARD,
            border_width=1,
            border_color=colors.BORDER,
            corner_radius=8
        )

        container.pack(
            fill="both",
            expand=True,
            padx=24,
            pady=24
        )

        title = ctk.CTkLabel(
            container,
            text=self.product.name,
            font=fonts.TITLE,
            text_color=colors.TEXT_PRIMARY
        )

        title.pack(
            anchor="w",
            padx=24,
            pady=(24, 28)
        )

        self.section_title(container, "Product Information")

        product_info = ctk.CTkFrame(
            container,
            fg_color="transparent"
        )

        product_info.pack(
            fill="x",
            padx=24,
            pady=(0, 24)
        )

        self.info_row(product_info, "Current Price", self.value("current_price"))
        self.info_row(product_info, "Original Price", self.value("original_price"))
        self.info_row(product_info, "Discount", self.value("discount"))
        self.info_row(product_info, "Stock", self.value("stock"))
        self.info_row(product_info, "Last Checked", "Just now")

        self.section_title(container, "Monitoring Information")

        monitoring_info = ctk.CTkFrame(
            container,
            fg_color="transparent"
        )

        monitoring_info.pack(
            fill="x",
            padx=24,
            pady=(0, 24)
        )

        self.info_row(monitoring_info, "Shop ID", self.value("shop_id"))
        self.info_row(monitoring_info, "Item ID", self.value("item_id"))
        self.info_row(monitoring_info, "Model ID", self.value("model_id"))

        close_button = ctk.CTkButton(
            container,
            text="Close",
            width=120,
            height=36,
            fg_color=colors.PRIMARY,
            hover_color=colors.PRIMARY_HOVER,
            font=fonts.BUTTON,
            command=self.destroy
        )

        close_button.pack(
            side="bottom",
            anchor="e",
            padx=24,
            pady=(0, 24)
        )

    def section_title(self, parent, text):
        ctk.CTkLabel(
            parent,
            text=text,
            font=fonts.HEADING,
            text_color=colors.TEXT_PRIMARY
        ).pack(
            anchor="w",
            padx=24,
            pady=(0, 10)
        )

    def info_row(self, parent, label, value):
        frame = ctk.CTkFrame(
            parent,
            fg_color="transparent"
        )

        frame.pack(
            fill="x",
            pady=6
        )

        ctk.CTkLabel(
            frame,
            text=label,
            font=fonts.BODY,
            text_color=colors.TEXT_SECONDARY
        ).pack(side="left")

        ctk.CTkLabel(
            frame,
            text=value,
            font=fonts.BODY,
            text_color=colors.TEXT_PRIMARY
        ).pack(side="right")

    def value(self, field_name):
        value = getattr(self.product, field_name, "")

        return str(value) if value else "--"
