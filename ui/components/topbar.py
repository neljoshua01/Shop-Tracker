import customtkinter as ctk

from ui import colors, fonts


class TopBar(ctk.CTkFrame):

    def __init__(self, master, add_callback):
        super().__init__(
            master,
            fg_color=colors.BACKGROUND,
            corner_radius=0
        )

        self.add_callback = add_callback

        self.build_ui()

    def build_ui(self):
        self.url_entry = ctk.CTkEntry(
            self,
            height=44,
            font=fonts.BODY,
            fg_color=colors.INPUT,
            border_color=colors.BORDER,
            placeholder_text="Search or paste Shopee Product URL here..."
        )

        self.url_entry.pack(
            side="left",
            fill="x",
            expand=True,
            padx=(0, 15)
        )

        self.add_button = ctk.CTkButton(
            self,
            text="+  Add Product",
            width=150,
            height=44,
            fg_color=colors.PRIMARY,
            hover_color=colors.PRIMARY_HOVER,
            font=fonts.BUTTON,
            command=self.add_callback
        )

        self.add_button.pack(side="right")

    def get_url(self):
        return self.url_entry.get()

    def clear(self):
        self.url_entry.delete(0, "end")
        self.url_entry.focus_set()

    def focus_url(self):
        self.url_entry.focus_set()