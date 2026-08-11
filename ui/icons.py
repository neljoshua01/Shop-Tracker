import os
from io import BytesIO
from pathlib import Path
from typing import Dict, Tuple

import cairosvg
import customtkinter as ctk
from PIL import Image


# =====================================================
# Cairo Configuration
# =====================================================

CAIRO_LIB = Path("/opt/homebrew/opt/cairo/lib")

if CAIRO_LIB.exists():
    current_dyld = os.environ.get("DYLD_LIBRARY_PATH", "")
    cairo_path = str(CAIRO_LIB)

    if cairo_path not in current_dyld.split(":"):
        os.environ["DYLD_LIBRARY_PATH"] = (
            f"{cairo_path}:{current_dyld}"
            if current_dyld
            else cairo_path
        )


# =====================================================
# V2 SVG Icon Registry
# =====================================================

ICON_DIR = (
    Path(__file__).resolve().parent.parent
    / "assets"
    / "icons"
)


# =====================================================
# Navigation
# =====================================================

DASHBOARD = ICON_DIR / "dashboard.svg"
PRODUCTS = ICON_DIR / "products.svg"
LOGS = ICON_DIR / "logs.svg"
ALERT = ICON_DIR / "alert.svg"
SETTINGS = ICON_DIR / "settings.svg"


# =====================================================
# Product / Purchase
# =====================================================

PRODUCT = ICON_DIR / "products.svg"
CART = ICON_DIR / "cart.svg"
DISCOUNT = ICON_DIR / "discount.svg"
TIME = ICON_DIR / "time.svg"
CART_MIRROR = ICON_DIR / "cart_mirror.svg"
CHECKOUT = ICON_DIR / "checkout.svg"
PURCHASE_PROFILE = ICON_DIR / "purchase_profile.svg"
PURCHASE_SUCCESS = ICON_DIR / "purchase_success.svg"


# =====================================================
# Monitoring / System
# =====================================================

MONITORING_ENGINE = ICON_DIR / "monitoring_engine.svg"
EXECUTION_ENGINE = ICON_DIR / "execution_engine.svg"
SYSTEM_RESPONSE_LOG = ICON_DIR / "system_response_log.svg"
API_SERVICES = ICON_DIR / "api_services.svg"
API_POLLER = ICON_DIR / "api_poller.svg"
PRODUCT_API = ICON_DIR / "product_api.svg"
SHOPEE_API = ICON_DIR / "shopee_api.svg"
STATE_MANAGER = ICON_DIR / "state_manager.svg"
CHROME_SESSION = ICON_DIR / "chrome_session.svg"
PROXY = ICON_DIR / "proxy.svg"


# =====================================================
# Controls / Status
# =====================================================

PLAY = ICON_DIR / "play.svg"
PAUSE = ICON_DIR / "pause.svg"
MORE = ICON_DIR / "more.svg"
NOTIFICATION = ICON_DIR / "notification.svg"
LOCK = ICON_DIR / "lock.svg"
OTP = ICON_DIR / "otp.svg"
PROFILE = ICON_DIR / "profile.svg"
ORDERS = ICON_DIR / "orders.svg"


# =====================================================
# Icon Sizes
# =====================================================

SIZE_SMALL = (18, 18)
SIZE_DEFAULT = (20, 20)
SIZE_LARGE = (24, 24)


# =====================================================
# Icon Cache
# =====================================================

_ICON_CACHE: Dict[
    Tuple[str, Tuple[int, int], str],
    ctk.CTkImage
] = {}


# =====================================================
# SVG Rendering
# =====================================================

def _load_svg_source(path: Path) -> str:
    """
    Read an SVG file and return its source text.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"Icon not found: {path}"
        )

    return path.read_text(
        encoding="utf-8"
    )


def _render_svg(
    path: Path,
    color: str,
    size: Tuple[int, int],
) -> Image.Image:
    """
    Render an SVG into a PIL image.

    V2 SVG icons use `currentColor`, so the requested
    UI color is substituted before CairoSVG renders
    the asset.
    """
    svg_source = _load_svg_source(path)

    svg_source = svg_source.replace(
        "currentColor",
        color,
    )

    png_bytes = cairosvg.svg2png(
        bytestring=svg_source.encode("utf-8"),
        output_width=size[0],
        output_height=size[1],
    )

    return Image.open(
        BytesIO(png_bytes)
    ).convert("RGBA")


# =====================================================
# Public Icon Loader
# =====================================================

def load_icon(
    icon: Path,
    color: str,
    size: Tuple[int, int] = SIZE_DEFAULT,
) -> ctk.CTkImage:
    """
    Load and cache a V2 SVG icon as a CustomTkinter image.

    Parameters
    ----------
    icon:
        SVG path from the semantic icon registry.

    color:
        Hex color used to replace `currentColor`.

    size:
        Rendered icon size in pixels.
    """
    cache_key = (
        str(icon.resolve()),
        size,
        color,
    )

    cached = _ICON_CACHE.get(cache_key)

    if cached is not None:
        return cached

    image = _render_svg(
        path=icon,
        color=color,
        size=size,
    )

    ctk_image = ctk.CTkImage(
        light_image=image,
        dark_image=image,
        size=size,
    )

    _ICON_CACHE[cache_key] = ctk_image

    return ctk_image


# =====================================================
# Path Helper
# =====================================================

def icon_path(icon: Path) -> str:
    """
    Return the filesystem path for an SVG icon.
    """
    return str(icon)