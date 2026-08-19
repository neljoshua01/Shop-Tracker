import customtkinter as ctk

from ui import colors, fonts
from ui.components.product_list import ProductList


class ProductsPage(ctk.CTkFrame):

    def __init__(
        self,
        master,
        stop_monitoring_callback,
    ):
        super().__init__(
            master,
            fg_color=colors.BACKGROUND
        )

        self.stop_monitoring_callback = stop_monitoring_callback

        self.build_ui()

    def build_ui(self):

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=1)

        # ==================================================
        # Page Header
        # ==================================================

        header = ctk.CTkFrame(
            self,
            fg_color="transparent"
        )

        header.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=20,
            pady=(20, 12)
        )

        header_left = ctk.CTkFrame(
            header,
            fg_color="transparent"
        )

        header_left.pack(
            side="left",
            fill="x",
            expand=True
        )

        ctk.CTkLabel(
            header_left,
            text="Products",
            font=fonts.TITLE,
            text_color=colors.TEXT_PRIMARY
        ).pack(
            anchor="w"
        )

        ctk.CTkLabel(
            header_left,
            text="Manage products currently being monitored.",
            font=fonts.BODY,
            text_color=colors.TEXT_SECONDARY
        ).pack(
            anchor="w",
            pady=(4, 0)
        )

        # Product count
        self.product_count_label = ctk.CTkLabel(
            header,
            text="0 products",
            font=fonts.SMALL_BOLD,
            text_color=colors.TEXT_SECONDARY
        )

        self.product_count_label.pack(
            side="right",
            padx=(10, 0),
            pady=(12, 0)
        )

        # ==================================================
        # Toolbar
        # ==================================================

        toolbar = ctk.CTkFrame(
            self,
            fg_color=colors.CARD,
            border_width=1,
            border_color=colors.BORDER,
            corner_radius=8
        )

        toolbar.grid(
            row=1,
            column=0,
            sticky="ew",
            padx=20,
            pady=(0, 12)
        )

        toolbar.grid_columnconfigure(0, weight=1)

        # Search
        self.search_entry = ctk.CTkEntry(
            toolbar,
            height=38,
            placeholder_text="Search monitored products...",
            fg_color=colors.INPUT,
            border_color=colors.BORDER,
            text_color=colors.TEXT_PRIMARY,
            placeholder_text_color=colors.TEXT_MUTED
        )

        self.search_entry.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=12,
            pady=12
        )

        # Filter
        self.filter_menu = ctk.CTkOptionMenu(
            toolbar,
            width=130,
            height=38,
            values=[
                "All Products",
                "In Stock",
                "Low Stock",
                "Out of Stock"
            ],
            fg_color=colors.SURFACE,
            button_color=colors.PRIMARY_SOFT,
            button_hover_color=colors.CARD_HOVER,
            text_color=colors.TEXT_PRIMARY
        )

        self.filter_menu.grid(
            row=0,
            column=1,
            padx=(0, 8),
            pady=12
        )

        # Sort
        self.sort_menu = ctk.CTkOptionMenu(
            toolbar,
            width=130,
            height=38,
            values=[
                "Recently Added",
                "Price: Low → High",
                "Price: High → Low",
                "Name: A → Z"
            ],
            fg_color=colors.SURFACE,
            button_color=colors.PRIMARY_SOFT,
            button_hover_color=colors.CARD_HOVER,
            text_color=colors.TEXT_PRIMARY
        )

        self.sort_menu.grid(
            row=0,
            column=2,
            padx=(0, 8),
            pady=12
        )

        # Add Product
        self.add_button = ctk.CTkButton(
            toolbar,
            text="+  Add Product",
            width=130,
            height=38,
            fg_color=colors.PRIMARY,
            hover_color=colors.PRIMARY_HOVER,
            text_color=colors.BUTTON_TEXT,
            font=fonts.BUTTON,
            command=self.add_product_placeholder
        )

        self.add_button.grid(
            row=0,
            column=3,
            padx=(0, 12),
            pady=12
        )

        # ==================================================
        # Product List Container
        # ==================================================

        list_container = ctk.CTkFrame(
            self,
            fg_color=colors.CARD,
            border_width=1,
            border_color=colors.BORDER,
            corner_radius=8
        )

        list_container.grid(
            row=2,
            column=0,
            sticky="nsew",
            padx=20,
            pady=(0, 20)
        )

        list_container.grid_columnconfigure(0, weight=1)
        list_container.grid_rowconfigure(1, weight=1)

        # ==================================================
        # Table Header
        # ==================================================

        table_header = ctk.CTkFrame(
            list_container,
            fg_color=colors.SURFACE,
            corner_radius=6
        )

        table_header.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=10,
            pady=10
        )

        columns = [
            ("PRODUCT", 5),
            ("STOCK", 2),
            ("AUTO CHECKOUT", 2),
            ("TARGET PRICE", 2),
            ("CURRENT PRICE", 2),
            ("LAST CHECKED", 2),
            ("", 1),
        ]

        for index, (text, weight) in enumerate(columns):

            table_header.grid_columnconfigure(
                index,
                weight=weight
            )

            ctk.CTkLabel(
                table_header,
                text=text,
                font=fonts.SMALL_BOLD,
                text_color=colors.TEXT_MUTED,
                anchor="w"
            ).grid(
                row=0,
                column=index,
                sticky="ew",
                padx=10,
                pady=9
            )

        # ==================================================
        # Product List
        # ==================================================

        self.products_frame = ProductList(
            list_container,
            stop_callback=self.stop_monitoring_callback,
            fg_color="transparent"
        )

        self.products_frame.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=10,
            pady=(0, 10)
        )

    # ==================================================
    # Placeholder Actions
    # ==================================================

    def add_product_placeholder(self):

        # Add Product functionality remains connected
        # to the Dashboard for now.
        pass