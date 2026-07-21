from pathlib import Path
from PIL import Image
import customtkinter as ctk

ICON_DIR = Path(__file__).parent.parent / "assets" / "icons"

PRODUCT = ctk.CTkImage(
    Image.open(ICON_DIR / "box.png"),
    size=(24, 24)
)

VIEW = ctk.CTkImage(
    Image.open(ICON_DIR / "eye.png"),
    size=(18, 18)
)

STOP = ctk.CTkImage(
    Image.open(ICON_DIR / "trash.png"),
    size=(18, 18)
)

TIME = ctk.CTkImage(
    Image.open(ICON_DIR / "time.png"),
    size=(18, 18)
)

DISCOUNT = ctk.CTkImage(
    Image.open(ICON_DIR / "discount.png"),
    size=(18, 18)
)

TAG = ctk.CTkImage(
    Image.open(ICON_DIR / "tag.png"),
    size=(18, 18)
)

CART = ctk.CTkImage(
    Image.open(ICON_DIR / "cart.png"),
    size=(18, 18)
)