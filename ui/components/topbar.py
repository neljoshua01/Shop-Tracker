import customtkinter as ctk

from ui import colors, fonts


class TopBar(ctk.CTkFrame):

    def __init__(self, master, add_callback, purchase_profile_callback=None):
        super().__init__(
            master,
            fg_color=colors.TOPBAR,
            border_width=1,
            border_color=colors.BORDER,
            corner_radius=10,
            height=62
        )

        self.pack_propagate(False)
        self.add_callback = add_callback
        self.purchase_profile_callback = purchase_profile_callback

        self.build_ui()

    def build_ui(self):
        self.url_entry = ctk.CTkEntry(
            self,
            height=42,
            font=fonts.BODY,
            fg_color=colors.INPUT,
            border_color=colors.INPUT_BORDER,
            border_width=1,
            placeholder_text="Quick monitor a Shopee Product URL..."
        )

        self.url_entry.pack(
            side="left",
            fill="x",
            expand=True,
            padx=(10, 10),
            pady=9
        )

        self.add_button = ctk.CTkButton(
            self,
            text="+  Add Purchase Profile",
            width=194,
            height=42,
            fg_color=colors.PRIMARY,
            hover_color=colors.PRIMARY_HOVER,
            border_width=1,
            border_color=colors.PRIMARY_GLOW,
            text_color=colors.BUTTON_TEXT,
            font=fonts.BUTTON,
            command=self.purchase_profile_callback or self.add_callback
        )

        self.add_button.pack(
            side="right",
            padx=(0, 10),
            pady=9
        )

    def get_url(self):
        return self.url_entry.get()

    def clear(self):
        self.url_entry.delete(0, "end")
        self.url_entry.focus_set()

    def focus_url(self):
        self.url_entry.focus_set()
