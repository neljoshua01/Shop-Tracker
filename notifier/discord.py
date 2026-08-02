import ssl
import certifi
import aiohttp
from datetime import datetime


class DiscordNotifier:

    def __init__(self, webhook):

        self.webhook = webhook


    async def send_message(self, message):

        if not self.webhook:

            print("No Discord webhook configured.")

            return False

        payload = {
            "content": message
        }

        ssl_context = ssl.create_default_context(
            cafile=certifi.where()
        )

        connector = aiohttp.TCPConnector(
            ssl=ssl_context
        )

        async with aiohttp.ClientSession(
            connector=connector
        ) as session:

            async with session.post(
                self.webhook,
                json=payload
            ) as response:

                if response.status == 204:

                    print("✓ Discord notification sent.")

                    return True

                print(f"Discord error: {response.status}")

                return False
    async def send_dry_run(self, summary):
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        message = f"""
    🟡 **SHOP TRACKER — DRY RUN**

    🕒 **Time**
    {timestamp}

    📦 **Product**
    {summary["product"]}

    🏪 **Seller**
    {summary["seller"]}

    🎨 **Variation**
    {summary["variation"]}

    🔢 **Quantity**
    {summary["quantity"]}

    🎯 **Target Price**
    ₱{summary["target_price"]}

    💰 **Subtotal**
    ₱{summary["subtotal"]}

    🚚 **Shipping**
    ₱{summary["shipping"]}

    💵 **Total**
    ₱{summary["total"]}

    💳 **Payment**
    {summary["payment"]}

    🔗 **Product Link**
    {summary["url"]}

    ━━━━━━━━━━━━━━━━━━━━━━

    ⚠️ SAFE MODE ENABLED

    No purchase was submitted.
    """
        await self.send_message(message)
