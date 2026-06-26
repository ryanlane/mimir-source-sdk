"""Example Mimir content source using the mimir-source-sdk.

This channel ships three built-in test patterns and serves as both:
  1. A working reference you can install into Mimir immediately.
  2. A template you can copy and replace render() with your own logic.

Install by copying this directory into your Mimir channels folder:
    cp -r example/ /var/opt/mimir/mimir-api/channels/test-pattern/

Then restart the Mimir server and the channel will appear in Sources.
"""

from __future__ import annotations

from typing import Any

from mimir_source_sdk import ChannelInfo, MimirChannel, TestImageGenerator

# This is the class the Mimir host will instantiate.
# The name must match `class_name` in plugin.json.
ChannelClass = None  # set at bottom of file after class definition


class TestPatternChannel(MimirChannel):
    """Generates diagnostic test images.

    Settings (configurable from the Mimir UI):
        pattern   - Which test image to render.
                    "color_bars" | "checkerboard" | "debug_card"
                    Default: "color_bars"
        label     - Text label shown in the footer of color_bars and
                    checkerboard images. Default: "Test Pattern"
    """

    info = ChannelInfo(
        id="com.mimir.testpattern",
        name="Test Pattern",
        description="Diagnostic test images: color bars, checkerboard, and debug card.",
        version="1.0.0",
        author="Mimir",
        icon="🧪",
        tags=["debug", "test", "developer"],
    )

    default_settings: dict[str, Any] = {
        "pattern": "color_bars",
        "label": "Test Pattern",
    }

    async def render(self, width: int, height: int, settings: dict[str, Any]) -> bytes:
        pattern = settings.get("pattern", "color_bars")
        label = settings.get("label", "Test Pattern")

        # Pass the full settings dict as request_data so the debug card
        # can show what settings are currently in effect.
        request_data = {"resolution": [width, height], "settings": settings}

        if pattern == "checkerboard":
            return TestImageGenerator.checkerboard(
                width=width,
                height=height,
                label=label,
                request_data=request_data,
            )
        elif pattern == "debug_card":
            return TestImageGenerator.debug_card(
                width=width,
                height=height,
                request_data=request_data,
                channel_id=self.info.id,
                label=label,
            )
        else:
            # Default: color_bars
            return TestImageGenerator.color_bars(
                width=width,
                height=height,
                label=label,
                request_data=request_data,
            )


# Required: Mimir's plugin loader looks for `ChannelClass` in the module.
ChannelClass = TestPatternChannel
