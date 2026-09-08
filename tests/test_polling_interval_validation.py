"""Small production validation test for the 1-second polling option."""

from purchase.models.purchase_profile import PurchaseProfile
from purchase.services.purchase_profile_service import PurchaseProfileService


def main() -> int:
    one_second = PurchaseProfile(
        profile_name="Polling Validation",
        product=object(),
        polling_interval=1,
    )

    try:
        PurchaseProfileService.validate(one_second)
    except ValueError as exc:
        print(f"[PollingValidationTest] FAIL — 1 second was rejected: {exc}")
        return 1

    zero_seconds = PurchaseProfile(
        profile_name="Polling Validation",
        product=object(),
        polling_interval=0,
    )

    try:
        PurchaseProfileService.validate(zero_seconds)
    except ValueError:
        print("[PollingValidationTest] PASS — 1 second is accepted and 0 seconds is rejected.")
        return 0

    print("[PollingValidationTest] FAIL — 0 seconds was accepted.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
