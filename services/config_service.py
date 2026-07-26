import json
from pathlib import Path


class ConfigService:

    def __init__(self):

        self.file = Path("config.json")


    def load(self):

        default = {
            "armed_mode": False,
            "discord_enabled": True,
            "save_screenshot": True,
            "discord_webhook": ""
        }

        if not self.file.exists():

            self.save(default)

            return default

        with open(
            self.file,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        default.update(data)

        return default


    def save(self, config):

        with open(
            self.file,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                config,
                f,
                indent=4
            )