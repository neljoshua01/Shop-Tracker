import customtkinter as ctk

from ui import colors, fonts


class ActivityLogsPage(ctk.CTkFrame):

    def __init__(self, master):
        super().__init__(
            master,
            fg_color=colors.BACKGROUND
        )

        self.build_ui()

    def build_ui(self):

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

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

        ctk.CTkLabel(
            header,
            text="Activity Logs",
            font=fonts.TITLE,
            text_color=colors.TEXT_PRIMARY
        ).pack(
            anchor="w"
        )

        ctk.CTkLabel(
            header,
            text="View system responses and monitoring activity.",
            font=fonts.BODY,
            text_color=colors.TEXT_SECONDARY
        ).pack(
            anchor="w",
            pady=(4, 0)
        )

        # ==================================================
        # Log Container
        # ==================================================

        log_card = ctk.CTkFrame(
            self,
            fg_color=colors.CARD,
            border_width=1,
            border_color=colors.BORDER,
            corner_radius=8
        )

        log_card.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=20,
            pady=(0, 20)
        )

        log_card.grid_columnconfigure(0, weight=1)
        log_card.grid_rowconfigure(1, weight=1)

        # ==================================================
        # Log Header
        # ==================================================

        log_header = ctk.CTkFrame(
            log_card,
            fg_color="transparent"
        )

        log_header.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=16,
            pady=(16, 12)
        )

        log_header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            log_header,
            text="System Response Log",
            font=fonts.HEADING,
            text_color=colors.TEXT_PRIMARY
        ).grid(
            row=0,
            column=0,
            sticky="w"
        )

        self.clear_button = ctk.CTkButton(
            log_header,
            text="Clear",
            width=80,
            height=32,
            fg_color="transparent",
            hover_color=colors.CARD_HOVER,
            border_width=1,
            border_color=colors.BORDER,
            text_color=colors.TEXT_SECONDARY,
            font=fonts.BUTTON,
            command=self.clear_logs
        )

        self.clear_button.grid(
            row=0,
            column=1,
            sticky="e"
        )

        # ==================================================
        # Log Display
        # ==================================================

        self.log_text = ctk.CTkTextbox(
            log_card,
            fg_color=colors.SURFACE_LIGHT,
            border_width=1,
            border_color=colors.BORDER,
            corner_radius=6,
            font=fonts.SMALL,
            text_color=colors.TEXT_PRIMARY,
            wrap="none"
        )

        self.log_text.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=16,
            pady=(0, 16)
        )

        self.log_text.insert(
            "end",
            "No activity logs yet.\n"
        )

        self.log_text.configure(
            state="disabled"
        )

    # ==================================================
    # Log Controls
    # ==================================================

    def clear_logs(self):

        self.log_text.configure(
            state="normal"
        )

        self.log_text.delete(
            "1.0",
            "end"
        )

        self.log_text.insert(
            "end",
            "No activity logs yet.\n"
        )

        self.log_text.configure(
            state="disabled"
        )

    def append_log(self, message):

        self.log_text.configure(
            state="normal"
        )

        self.log_text.insert(
            "end",
            f"{message}\n"
        )

        self.log_text.see(
            "end"
        )

        self.log_text.configure(
            state="disabled"
        )