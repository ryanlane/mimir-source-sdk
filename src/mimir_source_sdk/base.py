"""MimirChannel — the base class every Mimir content source should extend."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from .images import TestImageGenerator
from .settings import SettingsManager

logger = logging.getLogger(__name__)


@dataclass
class ChannelInfo:
    """Metadata that identifies your channel in the Mimir UI and registry."""

    id: str
    name: str
    description: str
    version: str = "1.0.0"
    author: str = ""
    icon: str = "📺"
    tags: list[str] = field(default_factory=list)


class MimirChannel:
    """Base class for Mimir content source channels.

    Subclass this and override :meth:`render` — everything else is handled
    for you (router setup, manifest endpoint, settings persistence, error
    handling, fingerprinting).

    Minimal example::

        class WeatherChannel(MimirChannel):
            info = ChannelInfo(
                id="com.example.weather",
                name="Weather",
                description="Current conditions for any city",
                version="1.0.0",
            )
            default_settings = {"city": "New York", "units": "imperial"}

            async def render(self, width, height, settings):
                data = await fetch_weather(settings["city"])
                return render_weather_image(data, width, height)

    The host discovers your channel from ``plugin.json`` and calls
    ``request_image()`` whenever a display needs new content. You never need
    to call ``request_image()`` directly — just implement ``render()``.
    """

    #: Override this with a :class:`ChannelInfo` describing your channel.
    info: ChannelInfo = ChannelInfo(
        id="com.example.channel",
        name="Example Channel",
        description="A Mimir content source",
    )

    #: Default settings dict. Keys here appear in the Mimir settings UI
    #: and are passed to ``render()`` via the ``settings`` argument.
    default_settings: dict[str, Any] = {}

    def __init__(self, channel_dir: str | Path):
        self.channel_dir = Path(channel_dir)
        self.data_dir = self.channel_dir / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.settings = SettingsManager(self.data_dir, self.default_settings)
        self._router = self._build_router()

    # ------------------------------------------------------------------
    # Override this
    # ------------------------------------------------------------------

    async def render(self, width: int, height: int, settings: dict[str, Any]) -> bytes:
        """Generate and return image bytes for the given display resolution.

        This is the only method you *must* override. Return JPEG or PNG bytes.

        Args:
            width:    Display width in pixels (from the requesting screen).
            height:   Display height in pixels.
            settings: Merged channel settings (defaults + any user overrides).

        Returns:
            Raw image bytes. JPEG is strongly preferred for performance.

        The default implementation returns a color-bar test image so your
        channel is immediately functional before you write any real logic.
        """
        return TestImageGenerator.color_bars(
            width=width,
            height=height,
            label=self.info.name,
        )

    # ------------------------------------------------------------------
    # Lifecycle hooks (optional overrides)
    # ------------------------------------------------------------------

    def on_startup(self) -> None:
        """Called by the host after the router is mounted.

        Use this to start background threads, warm caches, or open connections.
        """

    async def on_shutdown(self) -> None:
        """Called by the host during application shutdown.

        Use this to stop background threads and release resources.
        """

    # ------------------------------------------------------------------
    # Protocol interface (do not normally need to override)
    # ------------------------------------------------------------------

    def get_router(self) -> APIRouter:
        return self._router

    def get_manifest(self) -> dict[str, Any]:
        return {
            "id": self.info.id,
            "name": self.info.name,
            "description": self.info.description,
            "version": self.info.version,
            "author": self.info.author,
            "icon": self.info.icon,
            "tags": self.info.tags,
            "healthy": True,
            "capabilities": {
                "supports_settings": bool(self.default_settings),
            },
        }

    async def request_image(
        self, request_data: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Called by the host to request a new image for a display.

        You rarely need to override this. Override :meth:`render` instead.
        """
        request_data = request_data or {}
        settings_override = request_data.get("settings", {}) or {}
        merged_settings = {**self.settings.all(), **settings_override}

        resolution = request_data.get("resolution") or [800, 600]
        width = int(resolution[0]) if len(resolution) >= 1 else 800
        height = int(resolution[1]) if len(resolution) >= 2 else 600

        try:
            image_bytes = await self.render(
                width=width, height=height, settings=merged_settings
            )
        except Exception as exc:
            logger.exception("render() raised an exception")
            return {"success": False, "error": str(exc)}

        fingerprint = hashlib.sha256(image_bytes).hexdigest()[:32]
        content_type = "image/png" if image_bytes[:4] == b"\x89PNG" else "image/jpeg"

        return {
            "success": True,
            "bytes": image_bytes,
            "content_type": content_type,
            "width": width,
            "height": height,
            "content_fingerprint": fingerprint,
            "preferred_transport": "bytes",
        }

    # ------------------------------------------------------------------
    # Router
    # ------------------------------------------------------------------

    def _build_router(self) -> APIRouter:
        router = APIRouter()

        @router.get("/manifest")
        def manifest() -> JSONResponse:
            return JSONResponse(self.get_manifest())

        @router.post("/request-image")
        async def request_image_endpoint(request: Request) -> Response:
            try:
                body = await request.json()
            except Exception:
                body = {}

            result = await self.request_image(body)

            if not result.get("success"):
                return JSONResponse(result, status_code=500)

            img_bytes = result["bytes"]
            content_type = result.get("content_type", "image/jpeg")
            fingerprint = result.get("content_fingerprint", "")

            return Response(
                content=img_bytes,
                media_type=content_type,
                headers={
                    "X-Image-Width": str(result.get("width", "")),
                    "X-Image-Height": str(result.get("height", "")),
                    "X-Content-Fingerprint": fingerprint,
                    "X-Channel-Id": self.info.id,
                },
            )

        @router.get("/settings")
        def get_settings() -> JSONResponse:
            return JSONResponse(self.settings.all())

        @router.post("/settings")
        async def update_settings(request: Request) -> JSONResponse:
            try:
                data = await request.json()
            except Exception:
                return JSONResponse({"error": "invalid JSON"}, status_code=400)
            self.settings.update(data)
            return JSONResponse({"success": True, "settings": self.settings.all()})

        return router
