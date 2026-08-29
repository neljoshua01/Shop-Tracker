import customtkinter as ctk

from ui import colors, fonts


class SettingsPage(ctk.CTkFrame):

    def __init__(
        self,
        master,
        save_callback=None
    ):
        super().__init__(
            master,
            fg_color=colors.BACKGROUND
        )

        self.save_callback = save_callback

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
            text="Settings",
            font=fonts.TITLE,
            text_color=colors.TEXT_PRIMARY
        ).pack(
            anchor="w"
        )

        ctk.CTkLabel(
            header,
            text="Configure monitoring, notifications, and checkout behavior.",
            font=fonts.BODY,
            text_color=colors.TEXT_SECONDARY
        ).pack(
            anchor="w",
            pady=(4, 0)
        )

        # ==================================================
        # Settings Container
        # ==================================================

        self.settings_card = ctk.CTkFrame(
            self,
            fg_color=colors.CARD,
            border_width=1,
            border_color=colors.BORDER,
            corner_radius=8
        )

        self.settings_card.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=20,
            pady=(0, 20)
        )

        self.settings_card.grid_columnconfigure(
            0,
            weight=1
        )

        # ==================================================
        # Discord Settings
        # ==================================================

        self.section_title(
            self.settings_card,
            "Discord Notifications"
        )

        discord_frame = ctk.CTkFrame(
            self.settings_card,
            fg_color="transparent"
        )

        discord_frame.pack(
            fill="x",
            padx=24,
            pady=(0, 24)
        )

        self.discord_enabled_switch = self.setting_switch(
            discord_frame,
            "Discord Notifications",
            "Send monitoring and checkout notifications to Discord.",
            True
        )

        self.discord_enabled_switch.pack(
            anchor="w",
            pady=8
        )

        ctk.CTkLabel(
            discord_frame,
            text="Discord Webhook",
            font=fonts.BODY,
            text_color=colors.TEXT_PRIMARY
        ).pack(
            anchor="w",
            pady=(16, 4)
        )

        self.discord_webhook_entry = ctk.CTkEntry(
            discord_frame,
            height=36,
            placeholder_text="https://discord.com/api/webhooks/..."
        )

        self.discord_webhook_entry.pack(
            fill="x"
        )

        # ==================================================
        # Monitoring Settings
        # ==================================================

        self.section_title(
            self.settings_card,
            "Monitoring"
        )

        monitoring_frame = ctk.CTkFrame(
            self.settings_card,
            fg_color="transparent"
        )

        monitoring_frame.pack(
            fill="x",
            padx=24,
            pady=(0, 24)
        )

        self.save_screenshot_switch = self.setting_switch(
            monitoring_frame,
            "Save Screenshots",
            "Save screenshots during monitoring and checkout verification.",
            True
        )

        self.save_screenshot_switch.pack(
            anchor="w",
            pady=8
        )

        # ==================================================
        # Save Button
        # ==================================================

        self.save_button = ctk.CTkButton(
            self.settings_card,
            text="Save Settings",
            width=140,
            height=36,
            fg_color=colors.PRIMARY,
            hover_color=colors.PRIMARY_HOVER,
            font=fonts.BUTTON,
            command=self.save_settings
        )

        self.save_button.pack(
            anchor="e",
            padx=24,
            pady=(0, 24)
        )

    # ==================================================
    # UI Helpers
    # ==================================================

    def section_title(self, parent, text):

        ctk.CTkLabel(
            parent,
            text=text,
            font=fonts.HEADING,
            text_color=colors.TEXT_PRIMARY
        ).pack(
            anchor="w",
            padx=24,
            pady=(20, 10)
        )

    def setting_switch(
        self,
        parent,
        title,
        description,
        default=False
    ):

        frame = ctk.CTkFrame(
            parent,
            fg_color="transparent"
        )

        switch = ctk.CTkSwitch(
            frame,
            text=title,
            font=fonts.BODY,
            text_color=colors.TEXT_PRIMARY
        )

        switch.pack(
            anchor="w"
        )

        if default:
            switch.select()

        ctk.CTkLabel(
            frame,
            text=description,
            font=fonts.SMALL,
            text_color=colors.TEXT_SECONDARY,
            justify="left"
        ).pack(
            anchor="w",
            padx=(28, 0),
            pady=(2, 0)
        )

        frame.switch = switch

        return frame

    # ==================================================
    # Settings
    # ==================================================

    def get_settings(self):

        return {
            "discord_enabled": bool(
                self.discord_enabled_switch.switch.get()
            ),

            "save_screenshot": bool(
                self.save_screenshot_switch.switch.get()
            ),

            "discord_webhook": (
                self.discord_webhook_entry.get().strip()
            )
        }

    def set_settings(self, settings):

        self.discord_enabled_switch.switch.deselect()
        self.save_screenshot_switch.switch.deselect()

        if settings.get("discord_enabled", True):
            self.discord_enabled_switch.switch.select()

        if settings.get("save_screenshot", True):
            self.save_screenshot_switch.switch.select()

        self.discord_webhook_entry.delete(
            0,
            "end"
        )

        self.discord_webhook_entry.insert(
            0,
            settings.get("discord_webhook", "")
        )

    def save_settings(self):

        settings = self.get_settings()

        if self.save_callback:
            self.save_callback(settings)
