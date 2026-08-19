import asyncio
import re
from datetime import datetime, timezone, timedelta
from execution.browser.browser_engine import BrowserEngine


OWNER = "deep_discount_test"

PRODUCT_URL = (
    "https://shopee.ph/"
    "DJI-Osmo-Nano-Ultra-Light-Magnetic-Mounting-1-1.3-Sensor-4K-60fps-143%C2%B0-View-IPX4-Splash"
    "-i.258376387.42768475832"
    "?extraParams=%7B%22display_model_id%22%3A253939254333%7D"
)

POLL_INTERVAL = 30
POLL_COUNT = 90


def php_price(value):
    if value is None or value <= 0:
        return None

    return value / 100000


def extract_display_model_id(url):
    match = re.search(r"display_model_id=(\d+)", url)

    if not match:
        return None

    return int(match.group(1))

PH_TIMEZONE = timezone(timedelta(hours=8))


def format_ph_time(epoch):
    if epoch is None:
        return "NONE"

    try:
        dt = datetime.fromtimestamp(
            epoch,
            tz=PH_TIMEZONE,
        )

        return dt.strftime(
            "%Y-%m-%d %I:%M:%S %p"
        )

    except Exception:
        return "INVALID"


def get_event_status(reminder_event):
    if not isinstance(reminder_event, dict):
        return "NO_EVENT"

    start_time = reminder_event.get(
        "start_time"
    )

    end_time = reminder_event.get(
        "end_time"
    )

    if start_time is None or end_time is None:
        return "NO_EVENT"

    now = datetime.now(
        PH_TIMEZONE
    ).timestamp()

    if now < start_time:
        return "UPCOMING"

    if start_time <= now <= end_time:
        return "LIVE"

    if now > end_time:
        return "ENDED"

    return "UNKNOWN"

def get_event_timing(reminder_event):
    if not isinstance(reminder_event, dict):
        return {
            "seconds_until_start": None,
            "seconds_until_end": None,
        }

    start_time = reminder_event.get("start_time")
    end_time = reminder_event.get("end_time")

    if start_time is None or end_time is None:
        return {
            "seconds_until_start": None,
            "seconds_until_end": None,
        }

    now = datetime.now(PH_TIMEZONE).timestamp()

    return {
        "seconds_until_start": int(start_time - now),
        "seconds_until_end": int(end_time - now),
    }


def get_deep_discount_state(data, display_model_id):

    item = data.get("item", {})
    models = item.get("models", [])

    target_model = None

    for model in models:

        if model.get("model_id") == display_model_id:
            target_model = model
            break

    if target_model is None:

        print(
            f"[TEST] WARNING: Model "
            f"{display_model_id} was not found."
        )

        return None

    model_id = target_model.get("model_id")
    model_name = target_model.get("name")

    price_raw = target_model.get("price")

    price_before_discount_raw = (
        target_model.get("price_before_discount")
    )

    bottom_banner = data.get("bottom_banner")

    if not isinstance(bottom_banner, dict):
        bottom_banner = {}

    deep_discount = bottom_banner.get(
        "deep_discount"
    )

    has_deep_discount = (
        isinstance(deep_discount, dict)
    )

    promotion_id = None
    promotion_price_raw = None

    skin = None
    reminder_event = None

    is_lpp = None

    if has_deep_discount:

        promotion_id = deep_discount.get(
            "promotion_id"
        )

        is_lpp = deep_discount.get(
            "is_lpp"
        )

        promotion_price = deep_discount.get(
            "promotion_price"
        )

        if isinstance(promotion_price, dict):

            promotion_price_raw = (
                promotion_price.get(
                    "single_value"
                )
            )

        skin = deep_discount.get("skin")

        reminder_event = (
            deep_discount.get(
                "reminder_event"
            )
        )
    
    event_status = get_event_status(
        reminder_event
    )

    event_timing = get_event_timing(
        reminder_event
    )

    observed_at = datetime.now(
        PH_TIMEZONE
    )

    observed_epoch = int(
        observed_at.timestamp()
    )

    has_promotion_price = (
        promotion_price_raw is not None
        and promotion_price_raw > 0
    )

    if has_deep_discount:

        if event_status == "LIVE":

            state = "DEEP_DISCOUNT_LIVE"

        elif event_status == "UPCOMING":

            state = "DEEP_DISCOUNT_UPCOMING"

        elif event_status == "ENDED":

            state = "DEEP_DISCOUNT_ENDED"

        else:

            state = "DEEP_DISCOUNT"

    else:

        state = "PROMOTION_INACTIVE"

    return {

        "model_id": model_id,

        "model_name": model_name,

        "price_raw": price_raw,

        "price_php": php_price(
            price_raw
        ),

        "price_before_discount_raw": (
            price_before_discount_raw
        ),

        "price_before_discount_php": (
            php_price(
                price_before_discount_raw
            )
        ),

        "deep_discount": has_deep_discount,

        "promotion_id": promotion_id,

        "promotion_price_raw": (
            promotion_price_raw
        ),

        "promotion_price_php": (
            php_price(
                promotion_price_raw
            )
        ),

        "skin": skin,

        "reminder_event": reminder_event,

        "event_status": event_status,

        "seconds_until_start": (
            event_timing["seconds_until_start"]
        ),

        "seconds_until_end": (
            event_timing["seconds_until_end"]
        ),

        "is_lpp": is_lpp,

        "state": state,
    }


def print_snapshot(snapshot, poll_number):

    print("\n")
    print("=" * 100)

    print(
        f"[TEST] DEEP DISCOUNT SNAPSHOT "
        f"#{poll_number}"
    )

    print("=" * 100)

    print(
        f"Model:                "
        f"{snapshot['model_name']}"
    )

    print(
        f"Model ID:             "
        f"{snapshot['model_id']}"
    )

    if snapshot["price_php"] is not None:

        print(
            f"PDP Price:            "
            f"₱{snapshot['price_php']:,.2f}"
        )

    else:

        print(
            "PDP Price:            NONE"
        )

    if (
        snapshot[
            "price_before_discount_php"
        ]
        is not None
    ):

        print(
            f"Price Before Disc.:   "
            f"₱{snapshot['price_before_discount_php']:,.2f}"
        )

    else:

        print(
            "Price Before Disc.:   NONE"
        )

    print(
        f"Deep Discount:        "
        f"{'ACTIVE' if snapshot['deep_discount'] else 'NONE'}"
    )

    print(
        f"Event Status:         "
        f"{snapshot['event_status']}"
    )

    if snapshot["seconds_until_start"] is not None:

        print(
            f"Seconds Until Start:  "
            f"{snapshot['seconds_until_start']}"
        )

    else:

        print(
            "Seconds Until Start:  NONE"
        )


    if snapshot["seconds_until_end"] is not None:

        print(  
            f"Seconds Until End:    "
            f"{snapshot['seconds_until_end']}"
        )

    else:

        print(
            "Seconds Until End:    NONE"
        )

    print(
        f"Promotion ID:         "
        f"{snapshot['promotion_id']}"
    )

    if (
        snapshot[
            "promotion_price_php"
        ]
        is not None
    ):

        print(
            f"Mega Sale Price:      "
            f"₱{snapshot['promotion_price_php']:,.2f}"
        )

    else:

        print(
            "Mega Sale Price:      NONE"
        )

    print(
        f"Is LPP:               "
        f"{snapshot['is_lpp']}"
    )

    if snapshot["skin"]:

        print(
            f"Pre-Hype Text:        "
            f"{snapshot['skin'].get('pre_hype_text')}"
        )

    else:

        print(
            "Pre-Hype Text:        NONE"
        )

    if snapshot["reminder_event"]:

        event = snapshot["reminder_event"]

        start_time = event.get(
            "start_time"
        )

        end_time = event.get(
            "end_time"
        )

        print(
            f"Event Start:          "
            f"{format_ph_time(start_time)}"
        )

        print(
            f"Event End:            "
            f"{format_ph_time(end_time)}"
        )

        if (
            start_time is not None
            and end_time is not None
        ):

            duration = (
                end_time - start_time
            )

            print(
                f"Event Duration:       "
                f"{duration} seconds"
            )

    else:

        print(
            "Reminder Event:       NONE"
        )

    print(
        f"STATE:                "
        f"{snapshot['state']}"
    )

    print("=" * 100)


def compare_states(previous, current):

    changes = {}

    fields = [

        "price_raw",

        "price_before_discount_raw",

        "deep_discount",

        "promotion_id",

        "promotion_price_raw",

        "skin",

        "reminder_event",

        "event_status",

        "seconds_until_start",

        "seconds_until_end",

        "is_lpp",

        "state",

    ]

    for field in fields:

        old_value = previous.get(field)

        new_value = current.get(field)

        if old_value != new_value:

            changes[field] = (
                old_value,
                new_value,
            )

    return changes


class DeepDiscountCollector:

    def __init__(self):

        self.latest_state = None

        self.response_event = (
            asyncio.Event()
        )

        self.display_model_id = None

    async def on_response(
        self,
        response,
    ):

        url = response.url

        if "/api/v4/pdp/get_pc" not in url:
            return

        if response.status != 200:
            return

        display_model_id = (
            extract_display_model_id(url)
        )

        if display_model_id is None:
            return

        self.display_model_id = (
            display_model_id
        )

        try:

            data = await response.json()

        except Exception as e:

            print(
                f"[TEST] Failed to parse "
                f"get_pc: {e}"
            )

            return

        response_data = data.get(
            "data"
        )

        if not isinstance(
            response_data,
            dict,
        ):

            return

        snapshot = (
            get_deep_discount_state(
                response_data,
                display_model_id,
            )
        )

        if snapshot is None:
            return

        self.latest_state = snapshot

        self.response_event.set()


async def collect_snapshot(
    browser,
    session,
    collector,
):

    collector.latest_state = None

    collector.response_event.clear()

    await session.page.reload(
        wait_until="domcontentloaded"
    )

    try:

        await asyncio.wait_for(
            collector.response_event.wait(),
            timeout=15,
        )

    except asyncio.TimeoutError:

        print(
            "[TEST] TIMEOUT: No get_pc "
            "response received."
        )

        return None

    return collector.latest_state

def get_poll_interval(snapshot):
    event_status = snapshot.get(
        "event_status"
    )

    seconds_until_start = snapshot.get(
        "seconds_until_start"
    )

    if event_status == "LIVE":
        return 3

    if event_status == "UPCOMING":

        if (
            seconds_until_start is not None
            and seconds_until_start <= 60
        ):
            return 3

        if (
            seconds_until_start is not None
            and seconds_until_start <= 300
        ):
            return 10

        return 30

    return 30


async def main():

    browser = BrowserEngine.instance()

    collector = (
        DeepDiscountCollector()
    )

    browser.register_response_callback(
        OWNER,
        collector.on_response,
    )

    try:

        print(
            "[TEST] Opening product page..."
        )

        session = (
            await browser.get_session(
                OWNER,
                PRODUCT_URL,
            )
        )

        print(
            "[TEST] Product page loaded."
        )

        print(
            f"[TEST] Poll interval: "
            f"{POLL_INTERVAL} seconds"
        )

        print(
            f"[TEST] Poll count: "
            f"{POLL_COUNT}"
        )

        previous_state = None

        for poll_number in range(
            1,
            POLL_COUNT + 1,
        ):

            print("\n")
            print("#" * 100)

            print(
                f"[TEST] STARTING POLL "
                f"{poll_number}/{POLL_COUNT}"
            )

            print("#" * 100)

            current_state = (
                await collect_snapshot(
                    browser,
                    session,
                    collector,
                )
            )

            if current_state is None:

                print(
                    "[TEST] Could not obtain "
                    "deep discount snapshot."
                )

            else:

                print_snapshot(
                    current_state,
                    poll_number,
                )

                if previous_state is None:

                    print(
                        "\n[TEST] BASELINE ESTABLISHED"
                    )

                    print(
                        f"Initial State: "
                        f"{current_state['state']}"
                    )

                else:

                    changes = compare_states(
                        previous_state,
                        current_state,
                    )

                    if not changes:

                        print(
                            "\n[TEST] NO CHANGE"
                        )

                        print(
                            f"State remains: "
                            f"{current_state['state']}"
                        )

                    else:

                        print("\n")

                        print(
                            "!" * 100
                        )

                        print(
                            "[TEST] STATE CHANGE DETECTED"
                        )

                        print(
                            f"Previous State: "
                            f"{previous_state['state']}"
                        )

                        print(
                            f"Current State:  "
                            f"{current_state['state']}"
                        )

                        print(
                            "\nChanged Fields:"
                        )

                        for field, values in (
                            changes.items()
                        ):

                            old_value, new_value = (
                                values
                            )

                            print(
                                f"  {field}:"
                            )

                            print(
                                f"    OLD: {old_value}"
                            )

                            print(
                                f"    NEW: {new_value}"
                            )

                        print(
                            "!" * 100
                        )

                previous_state = (
                    current_state
                )

            if (
                poll_number
                < POLL_COUNT
            ):

                next_poll_interval = get_poll_interval(
                    current_state
                )

                print(
                    f"\n[TEST] Next poll in "
                    f"{next_poll_interval} seconds..."
                )

                await asyncio.sleep(
                    next_poll_interval
                )

    finally:

        await browser.close_session(
            OWNER
        )

        await browser.disconnect()


if __name__ == "__main__":

    asyncio.run(main())