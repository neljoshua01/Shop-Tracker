import asyncio

from services.config_service import ConfigService
from notifier.discord import DiscordNotifier


async def main():

    config = ConfigService().load()

    notifier = DiscordNotifier(
        config["discord_webhook"]
    )

    await notifier.send_message(
        "🧪 **Shop Tracker Test**\n\nWebhook connected successfully."
    )


asyncio.run(main())