"""Test image generator for Mimir channel development.

Produces three types of diagnostic images that are immediately useful
when wiring up a new channel — no external API key required.

All methods return raw JPEG bytes ready to drop into a ``render()`` method.
"""

from __future__ import annotations

import io
import os
from datetime import datetime
from typing import Any

from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# Font helpers
# ---------------------------------------------------------------------------

_FONT_SEARCH_PATHS = [
    # Linux (common distros)
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    # macOS
    "/System/Library/Fonts/Helvetica.ttc",
    "/Library/Fonts/Arial Bold.ttf",
    # Windows
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/arial.ttf",
]


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in _FONT_SEARCH_PATHS:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()


# ---------------------------------------------------------------------------
# Color palette
# ---------------------------------------------------------------------------

# Mimir signature green
MIMIR_GREEN = (0, 255, 48)
DARK_BG = (11, 19, 20)
SURFACE = (22, 35, 37)
TEXT_PRIMARY = (220, 230, 220)
TEXT_DIM = (120, 145, 130)

SMPTE_BARS = [
    (192, 192, 192),  # White 75%
    (192, 192, 0),    # Yellow
    (0, 192, 192),    # Cyan
    (0, 192, 0),      # Green
    (192, 0, 192),    # Magenta
    (192, 0, 0),      # Red
    (0, 0, 192),      # Blue
]


def _to_jpeg(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=92)
    return buf.getvalue()


def _draw_info_footer(
    draw: ImageDraw.Draw,
    x: int,
    y: int,
    width: int,
    height: int,
    label: str,
    request_data: dict[str, Any] | None,
) -> None:
    """Draw a dark footer bar with timestamp, resolution, and channel label."""
    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d  %H:%M:%S")
    resolution = f"{width} × {height}"

    font_large = _font(max(14, height // 30))
    font_small = _font(max(11, height // 45))

    draw.rectangle([x, y, x + width, y + height], fill=DARK_BG)

    # Green accent line at top of footer
    draw.rectangle([x, y, x + width, y + 2], fill=MIMIR_GREEN)

    pad = max(8, width // 60)
    mid_y = y + height // 2

    draw.text((x + pad, mid_y - height // 4), timestamp, font=font_large, fill=TEXT_PRIMARY, anchor="lm")
    draw.text((x + width - pad, mid_y - height // 4), resolution, font=font_large, fill=MIMIR_GREEN, anchor="rm")

    if label:
        draw.text((x + pad, mid_y + height // 4), label, font=font_small, fill=TEXT_DIM, anchor="lm")

    if request_data:
        settings = request_data.get("settings", {})
        if settings:
            summary = "  ·  ".join(f"{k}: {v}" for k, v in list(settings.items())[:4])
            draw.text((x + width - pad, mid_y + height // 4), summary, font=font_small, fill=TEXT_DIM, anchor="rm")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class TestImageGenerator:
    """Generate diagnostic images for Mimir channel development.

    All methods are class methods — no instantiation needed::

        bytes = TestImageGenerator.color_bars(800, 600, label="My Channel")
        bytes = TestImageGenerator.checkerboard(1024, 768)
        bytes = TestImageGenerator.debug_card(480, 320, request_data=req)
    """

    @classmethod
    def color_bars(
        cls,
        width: int = 800,
        height: int = 600,
        label: str = "",
        request_data: dict[str, Any] | None = None,
    ) -> bytes:
        """Classic SMPTE-style color bars with a debug footer.

        The footer shows the current timestamp, resolution, channel label,
        and a summary of any settings passed in ``request_data``.

        Good default render for any new channel — proves the pipeline
        is working before you write real content-fetching code.
        """
        img = Image.new("RGB", (width, height), DARK_BG)
        draw = ImageDraw.Draw(img)

        footer_h = max(60, height // 6)
        bar_h = height - footer_h
        bar_w = width // len(SMPTE_BARS)

        for i, color in enumerate(SMPTE_BARS):
            x0 = i * bar_w
            x1 = x0 + bar_w if i < len(SMPTE_BARS) - 1 else width
            draw.rectangle([x0, 0, x1, bar_h], fill=color)

        # Thin white grid lines between bars
        for i in range(1, len(SMPTE_BARS)):
            draw.line([(i * bar_w, 0), (i * bar_w, bar_h)], fill=(255, 255, 255, 80), width=1)

        # Crosshair at center of bar area
        cx, cy = width // 2, bar_h // 2
        cross = max(20, min(width, bar_h) // 10)
        draw.line([(cx - cross, cy), (cx + cross, cy)], fill=(0, 0, 0), width=3)
        draw.line([(cx, cy - cross), (cx, cy + cross)], fill=(0, 0, 0), width=3)
        draw.line([(cx - cross, cy), (cx + cross, cy)], fill=(255, 255, 255), width=1)
        draw.line([(cx, cy - cross), (cx, cy + cross)], fill=(255, 255, 255), width=1)

        _draw_info_footer(draw, 0, bar_h, width, footer_h, label, request_data)
        return _to_jpeg(img)

    @classmethod
    def checkerboard(
        cls,
        width: int = 800,
        height: int = 600,
        cell_size: int | None = None,
        label: str = "",
        request_data: dict[str, Any] | None = None,
    ) -> bytes:
        """Black and white checkerboard for geometry and alignment verification.

        Useful for checking:
        - That your display client is rendering at the correct resolution
        - That aspect ratio is correct (squares should look square)
        - That there's no unwanted stretching or cropping

        The footer shows timestamp and resolution.
        """
        if cell_size is None:
            cell_size = max(20, min(width, height) // 12)

        footer_h = max(60, height // 6)
        checker_h = height - footer_h

        img = Image.new("RGB", (width, height), DARK_BG)
        draw = ImageDraw.Draw(img)

        light = (200, 210, 200)
        dark = (40, 55, 45)

        cols = (width // cell_size) + 1
        rows = (checker_h // cell_size) + 1

        for row in range(rows):
            for col in range(cols):
                color = light if (row + col) % 2 == 0 else dark
                x0, y0 = col * cell_size, row * cell_size
                x1, y1 = min(x0 + cell_size, width), min(y0 + cell_size, checker_h)
                draw.rectangle([x0, y0, x1, y1], fill=color)

        # Corner labels
        font = _font(max(11, cell_size // 2))
        margin = 6
        corner_labels = [
            ((margin, margin), "lt", "ls"),   # left anchor, top
            ((width - margin, margin), "rt", "rs"),
            ((margin, checker_h - margin), "lb", "ls"),
            ((width - margin, checker_h - margin), "rb", "rs"),
        ]
        for (cx, cy), anchor, _ in corner_labels:
            draw.text((cx, cy), f"{cx},{cy}", font=font, fill=MIMIR_GREEN, anchor=anchor)

        # Center crosshair
        cx, cy = width // 2, checker_h // 2
        cross = cell_size * 2
        draw.line([(cx - cross, cy), (cx + cross, cy)], fill=MIMIR_GREEN, width=2)
        draw.line([(cx, cy - cross), (cx, cy + cross)], fill=MIMIR_GREEN, width=2)
        draw.ellipse([cx - 4, cy - 4, cx + 4, cy + 4], fill=MIMIR_GREEN)

        _draw_info_footer(draw, 0, checker_h, width, footer_h, label, request_data)
        return _to_jpeg(img)

    @classmethod
    def debug_card(
        cls,
        width: int = 800,
        height: int = 600,
        request_data: dict[str, Any] | None = None,
        channel_id: str = "",
        label: str = "",
    ) -> bytes:
        """Full-screen debug card showing all channel state.

        Displays:
        - Current date and time (large, prominent)
        - Display resolution
        - Channel ID
        - All settings passed in ``request_data``
        - Raw ``request_data`` keys for inspection

        Use this during development to verify that Mimir is passing the
        right settings and resolution to your channel.
        """
        request_data = request_data or {}
        img = Image.new("RGB", (width, height), DARK_BG)
        draw = ImageDraw.Draw(img)

        # Background surface panel with slight offset
        pad = max(12, width // 40)
        draw.rectangle([pad, pad, width - pad, height - pad], fill=SURFACE)

        # Green accent bar at top
        bar_h = max(4, height // 80)
        draw.rectangle([pad, pad, width - pad, pad + bar_h], fill=MIMIR_GREEN)

        now = datetime.now()
        time_str = now.strftime("%H:%M:%S")
        date_str = now.strftime("%A, %B %-d %Y")

        # Time — large and centered in top half
        time_font_size = max(32, min(width, height) // 5)
        time_font = _font(time_font_size)
        date_font = _font(max(14, time_font_size // 4))
        meta_font = _font(max(11, time_font_size // 6))

        center_x = width // 2
        time_y = height * 2 // 5

        draw.text((center_x, time_y), time_str, font=time_font, fill=TEXT_PRIMARY, anchor="mm")
        draw.text((center_x, time_y + time_font_size * 0.65), date_str, font=date_font, fill=TEXT_DIM, anchor="mm")

        # Divider
        div_y = time_y + time_font_size
        draw.line([(pad * 2, div_y), (width - pad * 2, div_y)], fill=(50, 70, 55), width=1)

        # Metadata block
        lines: list[tuple[str, tuple[int, int, int]]] = []

        res = request_data.get("resolution", [width, height])
        lines.append((f"resolution   {res[0]} × {res[1]}", TEXT_PRIMARY))

        if channel_id:
            lines.append((f"channel      {channel_id}", TEXT_DIM))

        if label:
            lines.append((f"label        {label}", TEXT_DIM))

        settings = request_data.get("settings", {})
        if settings:
            lines.append(("", TEXT_DIM))
            lines.append(("── settings ──────────────────", (60, 90, 70)))
            for k, v in settings.items():
                lines.append((f"{k:<16} {v}", TEXT_PRIMARY))

        other_keys = [k for k in request_data if k not in ("resolution", "settings")]
        if other_keys:
            lines.append(("", TEXT_DIM))
            lines.append(("── request data ───────────────", (60, 90, 70)))
            for k in other_keys:
                v = request_data[k]
                lines.append((f"{k:<16} {v}", TEXT_DIM))

        line_h = max(16, meta_font.size + 4) if hasattr(meta_font, "size") else 18
        text_start_y = div_y + pad

        for i, (line, color) in enumerate(lines):
            y = text_start_y + i * line_h
            if y + line_h > height - pad:
                break
            draw.text((pad * 2, y), line, font=meta_font, fill=color)

        # Resolution badge in bottom-right corner
        badge_font = _font(max(10, width // 60))
        badge_text = f"{width}×{height}"
        draw.text(
            (width - pad * 2, height - pad * 2),
            badge_text,
            font=badge_font,
            fill=MIMIR_GREEN,
            anchor="rb",
        )

        return _to_jpeg(img)
