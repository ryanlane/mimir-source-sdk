# mimir-source-sdk

The official SDK for building Mimir content source channels — the plugins that control what shows up on your displays.

A channel fetches content from anywhere (an API, a file, a database, a sensor) and returns an image. Mimir takes that image and pushes it to whichever displays are assigned to that channel.

---

## Quick start

### 1. Install the SDK

```bash
pip install mimir-source-sdk
```

Or add it to your channel's `requirements.txt`:

```
mimir-source-sdk>=1.0.0
```

### 2. Create your channel

```python
# channel.py
from mimir_source_sdk import MimirChannel, ChannelInfo

class MyChannel(MimirChannel):
    info = ChannelInfo(
        id="com.example.mychannel",
        name="My Channel",
        description="Shows something great on your displays.",
        version="1.0.0",
    )

    async def render(self, width, height, settings):
        # Return JPEG bytes. This is the only method you need to implement.
        image_bytes = await fetch_and_render_something(width, height)
        return image_bytes

ChannelClass = MyChannel
```

### 3. Add a plugin.json

```json
{
  "id": "com.example.mychannel",
  "name": "My Channel",
  "description": "Shows something great on your displays.",
  "version": "1.0.0",
  "type": "embedded",
  "entry_point": "channel.py",
  "class_name": "MyChannel"
}
```

### 4. Install into Mimir

Copy your channel directory into Mimir's channels folder and restart:

```bash
cp -r my-channel/ /var/opt/mimir/mimir-api/channels/
# then restart the Mimir server, or use the Sources > Install Source button in the UI
```

Your channel appears in the Mimir web UI under **Sources**.

---

## Shared utilities (`mimir_utils.py`)

The SDK ships a standalone utility module — `mimir_utils.py` — that provides the infrastructure patterns every channel needs: JSON caching, JSON-backed CRUD stores, settings dataclass helpers, and HTTP fetch wrappers.

### Two ways to use it

**Option A — pip install (recommended for new channels)**

Install the full SDK and import directly:

```python
from mimir_source_sdk import JsonCache, JsonStore, SettingsMixin, http_session, safe_fetch
```

Everything in `mimir_utils.py` is re-exported from the package root.

**Option B — vendor the file (zero external dependencies)**

Copy the single file into your channel directory:

```bash
curl -O https://raw.githubusercontent.com/ryanlane/mimir-source-sdk/main/mimir_utils.py
# or: cp mimir_utils.py my-channel/channels/my_channel/
```

Then import it directly:

```python
from mimir_utils import JsonCache, JsonStore, SettingsMixin, http_session, safe_fetch
```

No pip install, no network access needed at runtime. The only dependency is `requests` (for `http_session` and `safe_fetch`), which your channel almost certainly already lists in `requirements.txt`.

Use this option when your channel must be fully self-contained, when you're deploying to a Pi without reliable internet access, or when you want to pin to a specific version of the utilities independently of the SDK version.

> **Keeping in sync:** `mimir_utils.py` at the repo root and `src/mimir_source_sdk/mimir_utils.py` in the package are identical files. Any bug fix is committed to both in the same change.

### What's in `mimir_utils.py`

| Name | Type | What it does |
|---|---|---|
| `SettingsMixin` | class | Dataclass mixin — `to_dict()`, `to_public_dict()` (masks API keys), `from_dict()` |
| `JsonCache` | class | JSON-file-backed key/value cache with TTL — subclass and override `_make_key()` |
| `JsonStore` | class | JSON-file-backed CRUD list — subclass and implement `_from_dict()`, `_to_dict()` |
| `http_session()` | function | `requests.Session` with Mimir User-Agent pre-set |
| `safe_fetch()` | function | GET wrapper that returns `(data, error)` instead of raising |
| `validate_key_nonempty()` | function | Quick non-empty check for API keys — returns `{valid, error}` |

### Example — settings with masked API key

```python
from dataclasses import dataclass
from mimir_utils import SettingsMixin  # or: from mimir_source_sdk import SettingsMixin

@dataclass
class Settings(SettingsMixin):
    api_key: str = ""
    city: str = "New York"
    cache_minutes: int = 30

s = Settings.from_dict({"api_key": "sk-abc1234567890", "city": "Boston", "unknown": True})
s.to_public_dict()
# {"api_key": "••••••••7890", "city": "Boston", "cache_minutes": 30}
```

### Example — JSON cache with TTL

```python
from pathlib import Path
from mimir_utils import JsonCache

class WeatherCache(JsonCache):
    def _make_key(self, lat, lon, units):
        return f"{lat:.2f}_{lon:.2f}_{units}"

cache = WeatherCache(Path("data/weather_cache.json"))

if cache.needs_refresh(lat, lon, "metric", ttl_minutes=30):
    data = fetch_from_api(lat, lon)
    cache.set(data, lat, lon, "metric")

entry = cache.get(lat, lon, "metric")
```

### Example — CRUD store for sub-items

```python
from dataclasses import dataclass, asdict
from mimir_utils import JsonStore

@dataclass
class City:
    id: str
    name: str
    lat: float
    lon: float

class CityStore(JsonStore[City]):
    def _from_dict(self, d): return City(**d)
    def _to_dict(self, item): return asdict(item)

store = CityStore(Path("data/cities.json"))
city = store.create({"name": "Boston", "lat": 42.36, "lon": -71.06})
store.update(city.id, {"name": "Boston, MA"})
store.delete(city.id)
```

### Example — safe HTTP fetch

```python
from mimir_utils import http_session, safe_fetch

session = http_session()
data, err = safe_fetch(
    "https://api.openweathermap.org/data/2.5/weather",
    params={"q": "Boston", "appid": api_key},
    session=session,
)
if err:
    logger.error("Weather fetch failed: %s", err)
else:
    process(data)
```

---

## How channels work

```
┌─────────────┐     request-image      ┌──────────────────┐
│  Mimir host │ ──────────────────────▶│  Your channel    │
│             │  {resolution, settings} │                  │
│             │                         │  render()        │
│             │◀──────────────────────  │    ↓             │
│             │  JPEG bytes             │  return bytes    │
└─────────────┘                         └──────────────────┘
       │
       ▼
 pushes image to displays
```

When a display needs new content, Mimir calls your channel's `render()` method with:
- **width / height** — the display's pixel dimensions
- **settings** — the channel's current configuration (set by the user in the UI)

Your channel returns raw image bytes (JPEG strongly preferred). Mimir handles delivery.

---

## Project structure

A minimal channel has two files:

```
my-channel/
├── channel.py     ← your code (must export ChannelClass)
└── plugin.json    ← metadata and settings schema
```

A fuller channel might look like:

```
my-channel/
├── channel.py
├── plugin.json
├── requirements.txt
├── renderer.py    ← image rendering helpers
├── client.py      ← API client
└── data/          ← created automatically; stores settings.json and cache
```

---

## The render() method

This is the one method you must implement:

```python
async def render(self, width: int, height: int, settings: dict) -> bytes:
    ...
```

| Parameter  | Type    | Description                                              |
|------------|---------|----------------------------------------------------------|
| `width`    | `int`   | Target display width in pixels                           |
| `height`   | `int`   | Target display height in pixels                          |
| `settings` | `dict`  | Current channel settings (your defaults + user overrides)|

Return raw **JPEG bytes** (or PNG — JPEG is preferred for performance and file size).

### Generating images with Pillow

```python
import io
from PIL import Image, ImageDraw

async def render(self, width, height, settings):
    img = Image.new("RGB", (width, height), color=(20, 30, 40))
    draw = ImageDraw.Draw(img)
    draw.text((width // 2, height // 2), "Hello, Mimir!", fill=(255, 255, 255), anchor="mm")

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()
```

### Fetching from an external API

```python
import httpx
import io
from PIL import Image

async def render(self, width, height, settings):
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://api.example.com/image",
            params={"w": width, "h": height, "city": settings.get("city")},
        )
        resp.raise_for_status()

    img = Image.open(io.BytesIO(resp.content)).resize((width, height))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()
```

---

## Test images

The SDK ships a `TestImageGenerator` with three diagnostic images. Use these during development to verify your channel is wired up correctly before you write any real rendering logic.

```python
from mimir_source_sdk import TestImageGenerator

# Classic SMPTE color bars — proves the pipeline is working
bytes = TestImageGenerator.color_bars(width=800, height=600, label="My Channel")

# Checkerboard — verify resolution, aspect ratio, no stretching
bytes = TestImageGenerator.checkerboard(width=800, height=600)

# Debug card — shows timestamp, resolution, and all settings
bytes = TestImageGenerator.debug_card(width=800, height=600, request_data=req)
```

The default `render()` in `MimirChannel` already returns color bars, so your channel is immediately functional — open the Mimir web UI and you should see the test image on any display you assign.

### What each image shows

**color_bars**
- SMPTE 7-bar color pattern (white, yellow, cyan, green, magenta, red, blue)
- Center crosshair
- Footer: current timestamp · channel label · resolution

**checkerboard**
- Black and white grid squares
- Corner coordinates
- Center crosshair in Mimir green
- Footer: timestamp · resolution

**debug_card**
- Large digital clock (current time)
- Current date
- Display resolution
- Channel ID
- All settings passed in `request_data` as key–value pairs

Use the debug card when you want to confirm exactly what settings Mimir is sending to your channel.

---

## Channel settings

Define configurable settings so users can customize your channel from the Mimir web UI.

### Step 1 — set defaults on the class

```python
class WeatherChannel(MimirChannel):
    default_settings = {
        "city": "New York",
        "units": "imperial",
        "show_forecast": True,
    }
```

### Step 2 — use settings in render()

```python
async def render(self, width, height, settings):
    city = settings.get("city", "New York")
    units = settings.get("units", "imperial")
    ...
```

Settings are automatically persisted to `data/settings.json` between restarts. Users can update them from the Mimir UI (via the channel's `/settings` endpoint) and they'll be passed in on the next `render()` call.

### Step 3 — describe them in plugin.json

Add a JSON Schema under `settings.schema` so the Mimir UI can render a settings form:

```json
"settings": {
  "defaults": {
    "city": "New York",
    "units": "imperial"
  },
  "schema": {
    "type": "object",
    "properties": {
      "city": {
        "type": "string",
        "title": "City",
        "description": "City name for weather lookups."
      },
      "units": {
        "type": "string",
        "title": "Units",
        "enum": ["imperial", "metric"],
        "enumLabels": ["Imperial (°F)", "Metric (°C)"]
      },
      "show_forecast": {
        "type": "boolean",
        "title": "Show Forecast",
        "description": "Include a 3-day forecast below current conditions."
      }
    }
  }
}
```

---

## Lifecycle hooks

Override these to manage resources your channel needs:

```python
def on_startup(self) -> None:
    """Called once after the channel is loaded and its router is mounted."""
    self._client = MyApiClient(api_key=self.settings.get("api_key"))
    self._cache = {}

async def on_shutdown(self) -> None:
    """Called when the Mimir server is shutting down."""
    await self._client.close()
```

---

## plugin.json reference

```jsonc
{
  // Required
  "id": "com.yourname.channelname",   // Unique reverse-domain ID
  "name": "Channel Name",
  "description": "One sentence describing what this channel shows.",
  "version": "1.0.0",                 // Semantic versioning
  "type": "embedded",                 // Always "embedded"
  "entry_point": "channel.py",
  "class_name": "YourChannelClass",   // Must match ChannelClass in channel.py

  // Recommended
  "author": "Your Name",
  "icon": "🌤️",                      // Emoji or icon name
  "tags": ["weather", "live"],

  // How often Mimir requests a new image
  "update_schedule": {
    "unit": "minutes",                // "seconds" | "minutes" | "hours"
    "duration": 30
  },

  // Python dependencies (installed automatically on channel install)
  "requirements": {
    "python": ">=3.10",
    "dependencies": ["mimir-source-sdk>=1.0.0", "httpx>=0.24.0"]
  },

  // User-configurable settings (renders a form in the Mimir UI)
  "settings": {
    "defaults": { "city": "New York" },
    "schema": {
      "type": "object",
      "properties": {
        "city": { "type": "string", "title": "City" }
      }
    }
  }
}
```

---

## Accessing the settings manager directly

The `self.settings` attribute is a `SettingsManager` with a simple dict-like interface:

```python
# Read
city = self.settings.get("city", "New York")
all_settings = self.settings.all()

# Write (persisted immediately to data/settings.json)
self.settings.set("last_fetch", "2026-06-26T10:00:00")
self.settings.update({"city": "Boston", "units": "metric"})
```

This is useful for caching computed values, storing tokens, or persisting state across image requests.

---

## Local testing

You can test your channel without a full Mimir install using the standalone runner:

```python
# test_channel.py
import asyncio
from pathlib import Path
from channel import ChannelClass

async def main():
    channel = ChannelClass(str(Path(__file__).parent))

    # Simulate a request from Mimir
    result = await channel.request_image({
        "resolution": [1280, 800],
        "settings": {"city": "Boston"},
    })

    if result["success"]:
        Path("preview.jpg").write_bytes(result["bytes"])
        print(f"Rendered {result['width']}x{result['height']} — saved to preview.jpg")
    else:
        print("Error:", result["error"])

asyncio.run(main())
```

```bash
python test_channel.py
open preview.jpg
```

### Run as a standalone FastAPI server

Install Uvicorn and run your channel as a local server to test the full HTTP interface:

```bash
pip install uvicorn

# test_server.py
from fastapi import FastAPI
from pathlib import Path
from channel import ChannelClass

app = FastAPI()
channel = ChannelClass(str(Path(__file__).parent))
channel.on_startup()
app.include_router(channel.get_router(), prefix="/api/channels/test")
```

```bash
uvicorn test_server:app --reload
```

Then hit your channel's endpoints:

```bash
# Manifest
curl http://localhost:8000/api/channels/test/manifest

# Request an image (saves to disk)
curl -X POST http://localhost:8000/api/channels/test/request-image \
  -H "Content-Type: application/json" \
  -d '{"resolution": [800, 600], "settings": {"city": "Boston"}}' \
  --output preview.jpg

# Read settings
curl http://localhost:8000/api/channels/test/settings

# Update settings
curl -X POST http://localhost:8000/api/channels/test/settings \
  -H "Content-Type: application/json" \
  -d '{"city": "Chicago"}'
```

---

## Installing into Mimir

### Via the UI (recommended)

Go to **Sources → Install Source** in the Mimir web UI and upload a ZIP of your channel directory.

### Manually

```bash
# Copy your channel directory to the channels folder
cp -r my-channel/ /var/opt/mimir/mimir-api/channels/

# Install Python dependencies
pip install -r /var/opt/mimir/mimir-api/channels/my-channel/requirements.txt

# Restart the Mimir server (or use the hot-reload endpoint)
systemctl restart mimir
```

The server scans for new channels on startup. Your channel appears in **Sources** immediately.

---

## Full example

The `example/` directory contains a complete working channel (`TestPatternChannel`) that you can copy as a starting point. It demonstrates:

- `ChannelInfo` with all fields
- `default_settings` and settings schema in `plugin.json`
- `render()` that delegates to `TestImageGenerator` based on a setting
- All three test image types

```bash
# Copy the example into your Mimir channels folder to try it immediately
cp -r example/ /var/opt/mimir/mimir-api/channels/test-pattern/
```

---

## Publishing your channel

Once your channel is working, you can submit it to the [Mimir Plugin Registry](https://github.com/ryanlane/mimir-plugin-registry) so other Mimir users can install it with one click.

See the registry README for submission instructions. You'll need:

- A public GitHub repo containing your channel
- A valid `plugin.json` with a unique reverse-domain `id`
- A `README.md` describing what your channel does and any API keys or accounts it requires

---

## API reference

### `MimirChannel`

| Attribute / Method | Description |
|---|---|
| `info` | `ChannelInfo` — set this on your class |
| `default_settings` | `dict` — default values for user-configurable settings |
| `self.settings` | `SettingsManager` — read/write persisted settings |
| `self.channel_dir` | `Path` — your channel's directory |
| `self.data_dir` | `Path` — `channel_dir/data/` — safe place to write files |
| `async render(width, height, settings)` | **Override this** — return JPEG bytes |
| `on_startup()` | Override to run code after channel is loaded |
| `async on_shutdown()` | Override to clean up on server shutdown |

### `TestImageGenerator`

| Method | Description |
|---|---|
| `color_bars(width, height, label, request_data)` | SMPTE color bars + debug footer |
| `checkerboard(width, height, cell_size, label, request_data)` | Alignment grid |
| `debug_card(width, height, request_data, channel_id, label)` | Full-screen debug info |

### `SettingsManager`

| Method | Description |
|---|---|
| `get(key, default)` | Read a setting |
| `set(key, value)` | Write and persist a setting |
| `update(dict)` | Merge and persist multiple settings |
| `all()` | Return all settings as a dict |
