import asyncio
import re
from datetime import datetime, timezone, timedelta

from execution.browser.browser_engine import BrowserEngine


OWNER = "promotion_state_test"

PRODUCT_URL = (
    "https://shopee.ph/"
    "DJI-Osmo-Nano-Ultra-Light-Magnetic-Mounting-1-1.3-Sensor-4K-60fps-143%C2%B0-View-IPX4-Splash"
    "-i.258376387.42768475832"
    "?extraParams=%7B%22display_model_id%22%3A253939254333%7D"
)

POLL_INTERVAL = 15
POLL_COUNT = 5

PH_TIMEZONE = timezone(timedelta(hours=8))


def php_price(value):
    if value is None or value <= 0:
        return None

    return value / 100000


def extract_display_model_id(url):
    match = re.search(
        r"display_model_id=(\d+)",
        url,
    )

    if not match:
        return None

    return int(match.group(1))


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

    start_time = reminder_event.get("start_time")
    end_time = reminder_event.get("end_time")

    if start_time is None:
        return "NO_EVENT"

    now = datetime.now(
        PH_TIMEZONE
    ).timestamp()

    # Event has a start time but no end time.
    # This is valid for some preview events.
    if end_time is None:

        if now < start_time:
            return "UPCOMING"

        return "LIVE"

    # Normal event with both start and end.
    if now < start_time:
        return "UPCOMING"

    if start_time <= now <= end_time:
        return "LIVE"

    if now > end_time:
        return "ENDED"

    return "UNKNOWN"


def get_event_timing(start_time, end_time):

    if start_time is None and end_time is None:
        return {
            "seconds_until_start": None,
            "seconds_until_end": None,
        }

    now = datetime.now(
        PH_TIMEZONE
    ).timestamp()

    seconds_until_start = None
    seconds_until_end = None

    if start_time is not None:
        seconds_until_start = int(
            start_time - now
        )

    if end_time is not None:
        seconds_until_end = int(
            end_time - now
        )

    return {
        "seconds_until_start": seconds_until_start,
        "seconds_until_end": seconds_until_end,
    }


def extract_event_times(obj):
    """
    Try to find start/end timestamps from a promotion object.
    """

    if not isinstance(obj, dict):
        return None, None

    start_time = obj.get("start_time")
    end_time = obj.get("end_time")

    return start_time, end_time


def inspect_promotion_object(
    name,
    value,
):
    if not isinstance(value, dict):
        return {
            "name": name,
            "active": False,
            "promotion_id": None,
            "start_time": None,
            "end_time": None,
        }

    start_time, end_time = extract_event_times(
        value
    )

    return {
        "name": name,
        "active": True,
        "promotion_id": value.get(
            "promotion_id"
        ),
        "start_time": start_time,
        "end_time": end_time,
    }


def get_promotion_state(
    data,
    display_model_id,
):
    item = data.get(
        "item",
        {},
    )

    models = item.get(
        "models",
        [],
    )

    target_model = None

    for model in models:

        if (
            model.get("model_id")
            == display_model_id
        ):
            target_model = model
            break

    if target_model is None:

        print(
            f"[TEST] WARNING: Model "
            f"{display_model_id} "
            f"was not found."
        )

        return None

    # --------------------------------------------------
    # MODEL
    # --------------------------------------------------

    model_id = target_model.get(
        "model_id"
    )

    model_name = target_model.get(
        "name"
    )

    price_raw = target_model.get(
        "price"
    )

    price_before_discount_raw = (
        target_model.get(
            "price_before_discount"
        )
    )

    model_promotion_id = (
        target_model.get(
            "promotion_id"
        )
    )

    # --------------------------------------------------
    # MODEL PROMOTION TYPES
    # --------------------------------------------------

    promotion_types = []

    price_stocks = target_model.get(
        "price_stocks",
        [],
    )

    if isinstance(
        price_stocks,
        list,
    ):

        for price_stock in price_stocks:

            if not isinstance(
                price_stock,
                dict,
            ):
                continue

            promotion_type = (
                price_stock.get(
                    "promotion_type"
                )
            )

            if promotion_type is not None:

                promotion_types.append(
                    promotion_type
                )

    promotion_types = list(
        dict.fromkeys(
            promotion_types
        )
    )

    # --------------------------------------------------
    # PRODUCT PRICE PROMOTION
    # --------------------------------------------------

    product_price = data.get(
        "product_price",
        {},
    )

    if not isinstance(
        product_price,
        dict,
    ):
        product_price = {}

    price_promotion = (
        product_price.get(
            "price_promotion"
        )
    )

    if not isinstance(
        price_promotion,
        dict,
    ):
        price_promotion = {}

    price_single_promotion_id = (
        price_promotion.get(
            "price_single_promotion_id"
        )
    )

    price_single_promotion_type = (
        price_promotion.get(
            "price_single_promotion_type"
        )
    )

    # --------------------------------------------------
    # TOP-LEVEL PROMOTION OBJECTS
    # --------------------------------------------------

    flash_sale = data.get(
        "flash_sale"
    )

    flash_sale_preview = data.get(
        "flash_sale_preview"
    )

    deep_discount = data.get(
        "deep_discount"
    )

    exclusive_price = data.get(
        "exclusive_price"
    )

    # --------------------------------------------------
    # BANNERS
    # --------------------------------------------------

    top_banner = data.get(
        "top_banner"
    )

    if not isinstance(
        top_banner,
        dict,
    ):
        top_banner = {}

    bottom_banner = data.get(
        "bottom_banner"
    )

    if not isinstance(
        bottom_banner,
        dict,
    ):
        bottom_banner = {}

    top_flash_sale = (
        top_banner.get(
            "flash_sale"
        )
    )

    top_deep_discount = (
        top_banner.get(
            "deep_discount"
        )
    )

    bottom_flash_sale_preview = (
        bottom_banner.get(
            "flash_sale_preview"
        )
    )

    bottom_flash_sale = (
        bottom_banner.get(
            "flash_sale"
        )
    )

    bottom_deep_discount = (
        bottom_banner.get(
            "deep_discount"
        )
    )

    # --------------------------------------------------
    # PROMOTION OBJECT PRESENCE
    # --------------------------------------------------

    has_flash_sale = isinstance(
        flash_sale,
        dict,
    )

    has_flash_sale_preview = isinstance(
        flash_sale_preview,
        dict,
    )

    has_deep_discount = isinstance(
        deep_discount,
        dict,
    )

    has_exclusive_price = isinstance(
        exclusive_price,
        dict,
    )

    has_top_flash_sale = isinstance(
        top_flash_sale,
        dict,
    )

    has_top_deep_discount = isinstance(
        top_deep_discount,
        dict,
    )

    has_bottom_flash_sale_preview = (
        isinstance(
            bottom_flash_sale_preview,
            dict,
        )
    )

    has_bottom_flash_sale = isinstance(
        bottom_flash_sale,
        dict,
    )

    has_bottom_deep_discount = (
        isinstance(
            bottom_deep_discount,
            dict,
        )
    )

    # --------------------------------------------------
    # EVENT TIMING
    #
    # Priority:
    #   flash_sale
    #   flash_sale_preview
    #   deep_discount
    #   top banner
    #   bottom banner
    # --------------------------------------------------

    event_source = None
    event_start_time = None
    event_end_time = None

    candidates = [
        (
            "flash_sale",
            flash_sale,
        ),
        (
            "flash_sale_preview",
            flash_sale_preview,
        ),
        (
            "deep_discount",
            deep_discount,
        ),
        (
            "top_banner.flash_sale",
            top_flash_sale,
        ),
        (
            "top_banner.deep_discount",
            top_deep_discount,
        ),
        (
            "bottom_banner.flash_sale_preview",
            bottom_flash_sale_preview,
        ),
        (
            "bottom_banner.flash_sale",
            bottom_flash_sale,
        ),
        (
            "bottom_banner.deep_discount",
            bottom_deep_discount,
        ),
    ]

    for name, obj in candidates:

        start_time, end_time = (
            extract_event_times(obj)
        )

        if (
            start_time is not None
            or end_time is not None
        ):

            event_source = name

            event_start_time = start_time
            event_end_time = end_time

            break

    event_status = get_event_status(
        {
            "start_time": event_start_time,
            "end_time": event_end_time,
        }
    )

    event_timing = get_event_timing(
        event_start_time,
        event_end_time,
    )

    # --------------------------------------------------
    # PROMOTION IDS
    # --------------------------------------------------

    promotion_ids = []

    possible_ids = [
        model_promotion_id,
        price_single_promotion_id,
    ]

    for obj in [
        flash_sale,
        flash_sale_preview,
        deep_discount,
        exclusive_price,
        top_flash_sale,
        top_deep_discount,
        bottom_flash_sale_preview,
        bottom_flash_sale,
        bottom_deep_discount,
    ]:

        if isinstance(
            obj,
            dict,
        ):

            promotion_id = obj.get(
                "promotion_id"
            )

            if (
                promotion_id is not None
                and promotion_id != 0
            ):

                possible_ids.append(
                    promotion_id
                )

    for promotion_id in possible_ids:

        if (
            promotion_id is not None
            and promotion_id != 0
            and promotion_id not in promotion_ids
        ):

            promotion_ids.append(
                promotion_id
            )

    # --------------------------------------------------
    # STATE
    # --------------------------------------------------

    if has_flash_sale:

        state = "FLASH_SALE"

    elif has_top_flash_sale:

        state = "TOP_BANNER_FLASH_SALE"

    elif has_deep_discount:

        state = "DEEP_DISCOUNT"

    elif has_top_deep_discount:

        state = "TOP_BANNER_DEEP_DISCOUNT"

    elif has_exclusive_price:

        state = "EXCLUSIVE_PRICE"

    elif has_flash_sale_preview:

        state = "FLASH_SALE_PREVIEW"

    elif has_bottom_flash_sale_preview:

        state = "BOTTOM_BANNER_FLASH_SALE_PREVIEW"

    elif (
        model_promotion_id is not None
        and model_promotion_id != 0
    ):

        state = "MODEL_PROMOTION"

    elif (
        price_single_promotion_id is not None
        and price_single_promotion_id != 0
    ):

        state = "PRODUCT_PRICE_PROMOTION"

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

        "model_promotion_id": (
            model_promotion_id
        ),

        "price_promotion_id": (
            price_single_promotion_id
        ),

        "price_promotion_type": (
            price_single_promotion_type
        ),

        "promotion_ids": promotion_ids,

        "promotion_types": promotion_types,

        "flash_sale": has_flash_sale,

        "flash_sale_preview": (
            has_flash_sale_preview
        ),

        "deep_discount": (
            has_deep_discount
        ),

        "exclusive_price": (
            has_exclusive_price
        ),

        "top_banner_flash_sale": (
            has_top_flash_sale
        ),

        "top_banner_deep_discount": (
            has_top_deep_discount
        ),

        "bottom_banner_flash_sale_preview": (
            has_bottom_flash_sale_preview
        ),

        "bottom_banner_flash_sale": (
            has_bottom_flash_sale
        ),

        "bottom_banner_deep_discount": (
            has_bottom_deep_discount
        ),

        "event_source": event_source,

        "event_start_time": (
            event_start_time
        ),

        "event_end_time": (
            event_end_time
        ),

        "event_status": event_status,

        "seconds_until_start": (
            event_timing[
                "seconds_until_start"
            ]
        ),

        "seconds_until_end": (
            event_timing[
                "seconds_until_end"
            ]
        ),

        "state": state,
    }

def get_promotion_signature(snapshot):
    """
    Return only the fields that represent a meaningful
    promotion/product-price change.

    Dynamic countdown values are intentionally excluded.
    """

    return (
        snapshot.get("price_raw"),

        snapshot.get(
            "price_before_discount_raw"
        ),

        snapshot.get(
            "model_promotion_id"
        ),

        snapshot.get(
            "price_promotion_id"
        ),

        snapshot.get(
            "price_promotion_type"
        ),

        tuple(
            snapshot.get(
                "promotion_ids",
                [],
            )
        ),

        tuple(
            snapshot.get(
                "promotion_types",
                [],
            )
        ),

        snapshot.get(
            "flash_sale"
        ),

        snapshot.get(
            "flash_sale_preview"
        ),

        snapshot.get(
            "deep_discount"
        ),

        snapshot.get(
            "exclusive_price"
        ),

        snapshot.get(
            "top_banner_flash_sale"
        ),

        snapshot.get(
            "top_banner_deep_discount"
        ),

        snapshot.get(
            "bottom_banner_flash_sale_preview"
        ),

        snapshot.get(
            "bottom_banner_flash_sale"
        ),

        snapshot.get(
            "bottom_banner_deep_discount"
        ),

        snapshot.get(
            "state"
        ),
    )

def promotion_changed(
    previous,
    current,
):
    """
    Determine whether a meaningful promotion change occurred.

    Countdown/timing fields are intentionally ignored.
    """

    if previous is None:
        return True

    return (
        get_promotion_signature(previous)
        !=
        get_promotion_signature(current)
    )

def get_event_lifecycle_signature(snapshot):
    """
    Return the fields that describe the lifecycle of the
    currently detected promotion event.

    Countdown values are intentionally excluded.
    """

    return (
        snapshot.get("event_source"),
        snapshot.get("event_start_time"),
        snapshot.get("event_end_time"),
        snapshot.get("event_status"),
    )


def event_lifecycle_changed(
    previous,
    current,
):
    """
    Detect a meaningful change in the lifecycle of an event.

    Examples:
        UPCOMING -> LIVE
        LIVE -> ENDED
        NO_EVENT -> UPCOMING
        NO_EVENT -> LIVE

    Countdown changes do not trigger this.
    """

    if previous is None:
        return False

    previous_signature = (
        get_event_lifecycle_signature(
            previous
        )
    )

    current_signature = (
        get_event_lifecycle_signature(
            current
        )
    )

    return (
        previous_signature
        != current_signature
    )

def print_event_lifecycle_change(
    previous,
    current,
):
    previous_status = previous.get(
        "event_status"
    )

    current_status = current.get(
        "event_status"
    )

    previous_source = previous.get(
        "event_source"
    )

    current_source = current.get(
        "event_source"
    )

    print("\n")
    print("-" * 100)

    print(
        "[TEST] EVENT LIFECYCLE CHANGE"
    )

    print("-" * 100)

    print(
        f"Event Source: "
        f"{previous_source}"
        f" -> "
        f"{current_source}"
    )

    print(
        f"Event Status: "
        f"{previous_status}"
        f" -> "
        f"{current_status}"
    )

    print(
        f"Event Start:  "
        f"{format_ph_time(previous.get('event_start_time'))}"
        f" -> "
        f"{format_ph_time(current.get('event_start_time'))}"
    )

    print(
        f"Event End:    "
        f"{format_ph_time(previous.get('event_end_time'))}"
        f" -> "
        f"{format_ph_time(current.get('event_end_time'))}"
    )

    print("-" * 100)

def print_snapshot(
    snapshot,
    poll_number,
):

    print("\n")
    print("=" * 100)

    print(
        f"[TEST] PROMOTION SNAPSHOT "
        f"#{poll_number}"
    )

    print("=" * 100)

    print(
        f"Model:                         "
        f"{snapshot['model_name']}"
    )

    print(
        f"Model ID:                      "
        f"{snapshot['model_id']}"
    )

    if snapshot["price_php"] is not None:

        print(
            f"Price:                         "
            f"₱{snapshot['price_php']:,.2f}"
        )

    else:

        print(
            "Price:                         NONE"
        )

    if (
        snapshot[
            "price_before_discount_php"
        ]
        is not None
    ):

        print(
            f"Price Before Disc.:            "
            f"₱{snapshot['price_before_discount_php']:,.2f}"
        )

    else:

        print(
            "Price Before Disc.:            NONE"
        )

    print(
        f"Model Promotion ID:            "
        f"{snapshot['model_promotion_id']}"
    )

    print(
        f"Product Price Promotion ID:    "
        f"{snapshot['price_promotion_id']}"
    )

    print(
        f"Product Price Promotion Type:  "
        f"{snapshot['price_promotion_type']}"
    )

    print(
        f"All Promotion IDs:             "
        f"{snapshot['promotion_ids']}"
    )

    print(
        f"Promotion Types:               "
        f"{snapshot['promotion_types']}"
    )

    print()

    print(
        f"Flash Sale:                    "
        f"{'ACTIVE' if snapshot['flash_sale'] else 'NONE'}"
    )

    print(
        f"Flash Sale Preview:            "
        f"{'ACTIVE' if snapshot['flash_sale_preview'] else 'NONE'}"
    )

    print(
        f"Deep Discount:                 "
        f"{'ACTIVE' if snapshot['deep_discount'] else 'NONE'}"
    )

    print(
        f"Exclusive Price:               "
        f"{'ACTIVE' if snapshot['exclusive_price'] else 'NONE'}"
    )

    print()

    print(
        f"Top Banner Flash Sale:         "
        f"{'ACTIVE' if snapshot['top_banner_flash_sale'] else 'NONE'}"
    )

    print(
        f"Top Banner Deep Discount:      "
        f"{'ACTIVE' if snapshot['top_banner_deep_discount'] else 'NONE'}"
    )

    print(
        f"Bottom Banner Flash Preview:   "
        f"{'ACTIVE' if snapshot['bottom_banner_flash_sale_preview'] else 'NONE'}"
    )

    print(
        f"Bottom Banner Flash Sale:      "
        f"{'ACTIVE' if snapshot['bottom_banner_flash_sale'] else 'NONE'}"
    )

    print(
        f"Bottom Banner Deep Discount:   "
        f"{'ACTIVE' if snapshot['bottom_banner_deep_discount'] else 'NONE'}"
    )

    print()

    print(
        f"Event Source:                  "
        f"{snapshot['event_source']}"
    )

    print(
        f"Event Status:                  "
        f"{snapshot['event_status']}"
    )

    print(
        f"Event Start:                   "
        f"{format_ph_time(snapshot['event_start_time'])}"
    )

    print(
        f"Event End:                     "
        f"{format_ph_time(snapshot['event_end_time'])}"
    )

    print(
        f"Seconds Until Start:           "
        f"{snapshot['seconds_until_start']}"
    )

    print(
        f"Seconds Until End:             "
        f"{snapshot['seconds_until_end']}"
    )

    print()

    print(
        f"STATE:                         "
        f"{snapshot['state']}"
    )

    print("=" * 100)


def compare_states(
    previous,
    current,
):

    changes = {}

    fields = [
        "price_raw",
        "price_before_discount_raw",

        "model_promotion_id",
        "price_promotion_id",
        "price_promotion_type",

        "promotion_ids",
        "promotion_types",

        "flash_sale",
        "flash_sale_preview",
        "deep_discount",
        "exclusive_price",

        "top_banner_flash_sale",
        "top_banner_deep_discount",

        "bottom_banner_flash_sale_preview",
        "bottom_banner_flash_sale",
        "bottom_banner_deep_discount",

        "event_source",
        "event_start_time",
        "event_end_time",
        "event_status",
        "state",
    ]

    for field in fields:

        old_value = previous.get(
            field
        )

        new_value = current.get(
            field
        )

        if old_value != new_value:

            changes[field] = (
                old_value,
                new_value,
            )

    return changes

def classify_promotion_change(
    previous,
    current,
):
    """
    Classify the transition between two promotion snapshots.

    Returns:
        A string describing the type of change.
    """

    old_state = previous.get("state")
    new_state = current.get("state")

    old_price = previous.get("price_raw")
    new_price = current.get("price_raw")

    old_promotion_id = previous.get(
        "model_promotion_id"
    )
    new_promotion_id = current.get(
        "model_promotion_id"
    )

    old_price_promotion_id = previous.get(
        "price_promotion_id"
    )
    new_price_promotion_id = current.get(
        "price_promotion_id"
    )

    old_event_status = previous.get(
        "event_status"
    )
    new_event_status = current.get(
        "event_status"
    )

    # --------------------------------------------------
    # STATE ACTIVATED
    # --------------------------------------------------

    if (
        old_state == "PROMOTION_INACTIVE"
        and new_state != "PROMOTION_INACTIVE"
    ):
        return "PROMOTION_STARTED"

    # --------------------------------------------------
    # STATE ENDED
    # --------------------------------------------------

    if (
        old_state != "PROMOTION_INACTIVE"
        and new_state == "PROMOTION_INACTIVE"
    ):
        return "PROMOTION_ENDED"

    # --------------------------------------------------
    # PROMOTION TYPE CHANGED
    # --------------------------------------------------

    if old_state != new_state:
        return "PROMOTION_STATE_CHANGED"

    # --------------------------------------------------
    # PROMOTION ID CHANGED
    # --------------------------------------------------

    if (
        old_promotion_id
        != new_promotion_id
        or old_price_promotion_id
        != new_price_promotion_id
    ):
        return "PROMOTION_ID_CHANGED"

    # --------------------------------------------------
    # PRICE CHANGED
    # --------------------------------------------------

    if old_price != new_price:
        return "PRICE_CHANGED"

    # --------------------------------------------------
    # EVENT LIFECYCLE
    # --------------------------------------------------

    if old_event_status != new_event_status:
        return "EVENT_STATUS_CHANGED"

    return "OTHER_CHANGE"


class PromotionStateCollector:

    def __init__(self):

        self.latest_state = None
        self.latest_raw_data = None

        self.response_event = (
            asyncio.Event()
        )

        self.display_model_id = None

    async def on_response(
        self,
        response,
    ):

        url = response.url

        if (
            "/api/v4/pdp/get_pc"
            not in url
        ):
            return

        if response.status != 200:
            return

        display_model_id = (
            extract_display_model_id(
                url
            )
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

        # Keep the complete API data.
        self.latest_raw_data = response_data

        snapshot = (
            get_promotion_state(
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
    collector.latest_raw_data = None

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


async def main():

    browser = (
        BrowserEngine.instance()
    )

    collector = (
        PromotionStateCollector()
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
                    "promotion snapshot."
                )

            else:

                print_snapshot(
                    current_state,
                    poll_number,
                )

                if previous_state is None:

                    print(
                        "\n"
                        "[TEST] BASELINE ESTABLISHED"
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

                    meaningful_promotion_change = (
                        promotion_changed(
                            previous_state,
                            current_state,
                        )
                    )

                    meaningful_event_change = (
                        event_lifecycle_changed(
                            previous_state,
                            current_state,
                        )
                    )

                    if meaningful_promotion_change:

                        print("\n")
                        print("!" * 100)

                        print(
                            "[TEST] PROMOTION CHANGE DETECTED"
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

                        for (
                            field,
                            values,
                        ) in changes.items():

                            old_value, new_value = values

                            print(
                                f"  {field}:"
                            )

                            print(
                                f"    OLD: {old_value}"
                            )

                            print(
                                f"    NEW: {new_value}"
                            )

                        print("!" * 100)

                    elif meaningful_event_change:

                        print_event_lifecycle_change(
                            previous_state,
                            current_state,
                        )

                    else:

                        print(
                            "\n"
                            "[TEST] NO CHANGE"
                        )

                previous_state = current_state

            if (
                poll_number
                < POLL_COUNT
            ):

                print(
                    f"\n[TEST] Waiting "
                    f"{POLL_INTERVAL} seconds..."
                )

                await asyncio.sleep(
                    POLL_INTERVAL
                )

    finally:

        await browser.close_session(
            OWNER
        )

        await browser.disconnect()


if __name__ == "__main__":

    asyncio.run(main())