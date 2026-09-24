"""Cross-platform font discovery for the Qubi renderers."""
from functools import lru_cache
import os
from pathlib import Path

from PIL import ImageFont


ROOT = Path(__file__).resolve().parent


@lru_cache(maxsize=1)
def font_path() -> Path:
    windir = Path(os.environ.get("WINDIR", r"C:\Windows"))
    local_app_data = Path(os.environ.get("LOCALAPPDATA", ""))
    candidates = (
        ROOT / "assets" / "fonts" / "DejaVuSans-Bold.ttf",
        local_app_data / "Microsoft" / "Windows" / "Fonts" / "arialbd.ttf",
        windir / "Fonts" / "arialbd.ttf",
        windir / "Fonts" / "segoeuib.ttf",
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"),
        Path("/Library/Fonts/Arial Bold.ttf"),
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        "No supported bold font found. Add DejaVuSans-Bold.ttf to "
        "qubi_full_flow/assets/fonts/."
    )


@lru_cache(maxsize=64)
def font(size: int):
    return ImageFont.truetype(str(font_path()), size)
