from datetime import datetime, timezone, timedelta

from tests.test_deep_discount_monitor import (
    get_deep_discount_state,
    compare_states,
)


PH_TIMEZONE = timezone(timedelta(hours=8))

DISPLAY_MODEL_ID = 253939254333


def base_api_data():
    return {
        "item": {
            "models": [
                {
                    "model_id": DISPLAY_MODEL_ID,
                    "name": "Nano [128GB]",
                    "price": 1839000000,
                    "price_before_discount": None,
                }
            ]
        },
        "bottom_banner": {},
    }


def make_deep_discount_data(
    start_time,
    end_time,
    promotion_id=888888,
    promotion_price=1699000000,
):
    data = base_api_data()

    data["bottom_banner"]["deep_discount"] = {
        "promotion_id": promotion_id,
        "is_lpp": True,
        "promotion_price": {
            "single_value": promotion_price,
        },
        "skin": {
            "pre_hype_text": "8.8 Mega Sale"
        },
        "reminder_event": {
            "start_time": start_time,
            "end_time": end_time,
        },
    }

    return data


def make_inactive_data():
    return base_api_data()


def print_state(label, snapshot):
    print()
    print("=" * 100)
    print(label)
    print("=" * 100)

    print(
        f"State:                 {snapshot['state']}"
    )

    print(
        f"Deep Discount:         {snapshot['deep_discount']}"
    )

    print(
        f"Promotion ID:          {snapshot['promotion_id']}"
    )

    print(
        f"Promotion Price:       "
        f"{snapshot['promotion_price_php']}"
    )

    print(
        f"Event Status:          {snapshot['event_status']}"
    )

    print(
        f"Seconds Until Start:   "
        f"{snapshot['seconds_until_start']}"
    )

    print(
        f"Seconds Until End:     "
        f"{snapshot['seconds_until_end']}"
    )

    print("=" * 100)


def main():

    now = datetime.now(
        PH_TIMEZONE
    ).timestamp()

    #
    # State 1:
    # No promotion at all.
    #
    inactive_data = make_inactive_data()

    inactive = get_deep_discount_state(
        inactive_data,
        DISPLAY_MODEL_ID,
    )

    print_state(
        "REPLAY STATE 1 — INACTIVE",
        inactive,
    )

    assert inactive["state"] == (
        "PROMOTION_INACTIVE"
    )

    #
    # State 2:
    # Promotion exists, but it has not started.
    #
    upcoming_start = now + 300
    upcoming_end = now + 900

    upcoming_data = make_deep_discount_data(
        upcoming_start,
        upcoming_end,
    )

    upcoming = get_deep_discount_state(
        upcoming_data,
        DISPLAY_MODEL_ID,
    )

    print_state(
        "REPLAY STATE 2 — UPCOMING",
        upcoming,
    )

    assert upcoming["state"] == (
        "DEEP_DISCOUNT_UPCOMING"
    )

    #
    # State 3:
    # Promotion is currently live.
    #
    live_start = now - 60
    live_end = now + 600

    live_data = make_deep_discount_data(
        live_start,
        live_end,
    )

    live = get_deep_discount_state(
        live_data,
        DISPLAY_MODEL_ID,
    )

    print_state(
        "REPLAY STATE 3 — LIVE",
        live,
    )

    assert live["state"] == (
        "DEEP_DISCOUNT_LIVE"
    )

    #
    # State 4:
    # Promotion object still exists,
    # but its event has ended.
    #
    ended_start = now - 900
    ended_end = now - 60

    ended_data = make_deep_discount_data(
        ended_start,
        ended_end,
    )

    ended = get_deep_discount_state(
        ended_data,
        DISPLAY_MODEL_ID,
    )

    print_state(
        "REPLAY STATE 4 — ENDED",
        ended,
    )

    assert ended["state"] == (
        "DEEP_DISCOUNT_ENDED"
    )

    #
    # State 5:
    # Deep discount object disappears.
    #
    inactive_again = get_deep_discount_state(
        inactive_data,
        DISPLAY_MODEL_ID,
    )

    print_state(
        "REPLAY STATE 5 — INACTIVE AGAIN",
        inactive_again,
    )

    assert inactive_again["state"] == (
        "PROMOTION_INACTIVE"
    )

    #
    # Verify the transitions themselves.
    #
    transitions = [
        (
            inactive["state"],
            upcoming["state"],
        ),
        (
            upcoming["state"],
            live["state"],
        ),
        (
            live["state"],
            ended["state"],
        ),
        (
            ended["state"],
            inactive_again["state"],
        ),
    ]

    print()
    print("#" * 100)
    print("DEEP DISCOUNT STATE TRANSITIONS")
    print("#" * 100)

    for old_state, new_state in transitions:

        print(
            f"{old_state} -> {new_state}"
        )

    assert transitions == [
        (
            "PROMOTION_INACTIVE",
            "DEEP_DISCOUNT_UPCOMING",
        ),
        (
            "DEEP_DISCOUNT_UPCOMING",
            "DEEP_DISCOUNT_LIVE",
        ),
        (
            "DEEP_DISCOUNT_LIVE",
            "DEEP_DISCOUNT_ENDED",
        ),
        (
            "DEEP_DISCOUNT_ENDED",
            "PROMOTION_INACTIVE",
        ),
    ]

    #
    # Verify that compare_states detects
    # the important promotion changes.
    #
    print()
    print("#" * 100)
    print("CHANGE DETECTION")
    print("#" * 100)

    inactive_to_upcoming = compare_states(
        inactive,
        upcoming,
    )

    upcoming_to_live = compare_states(
        upcoming,
        live,
    )

    live_to_ended = compare_states(
        live,
        ended,
    )

    ended_to_inactive = compare_states(
        ended,
        inactive_again,
    )

    print(
        f"Inactive -> Upcoming: "
        f"{list(inactive_to_upcoming.keys())}"
    )

    print(
        f"Upcoming -> Live: "
        f"{list(upcoming_to_live.keys())}"
    )

    print(
        f"Live -> Ended: "
        f"{list(live_to_ended.keys())}"
    )

    print(
        f"Ended -> Inactive: "
        f"{list(ended_to_inactive.keys())}"
    )

    assert inactive_to_upcoming
    assert upcoming_to_live
    assert live_to_ended
    assert ended_to_inactive

    print()
    print("#" * 100)
    print("✅ DEEP DISCOUNT REPLAY PASSED")
    print("#" * 100)


if __name__ == "__main__":
    main()