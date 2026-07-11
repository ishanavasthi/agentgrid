"""Generate the demo's binary assets with pure stdlib (no PIL, no ffmpeg).

- make_mockup_png: the ISSUE-3 design mockup — SplitSathi stats page
  (green header bar, three white stat cards) as a real RGB PNG.
- make_demo_wav: the ISSUE-4 'voice note' — a short two-tone chime WAV,
  a legitimate audio payload for the multimodal Intake agent.

Tomorrow, replacing these files with a real Figma export / phone
recording upgrades the demo without touching code.
"""

from __future__ import annotations

import math
import struct
import wave
import zlib
from pathlib import Path

# ------------------------------------------------------------------ PNG

_GREEN = (15, 157, 88)      # #0f9d58 — the accent the Verifier checks for
_BG = (243, 246, 244)
_WHITE = (255, 255, 255)
_BORDER = (218, 224, 220)
_TEXTBAR = (198, 206, 201)
_DARKBAR = (60, 72, 66)

W, H = 640, 400


def _fill(pix, x0, y0, x1, y1, rgb):
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(W, x1), min(H, y1)
    for y in range(y0, y1):
        row = pix[y]
        for x in range(x0, x1):
            row[x] = rgb


def make_mockup_png(path: Path) -> Path:
    pix = [[_BG for _ in range(W)] for _ in range(H)]

    # header bar with a 'title' block
    _fill(pix, 0, 0, W, 64, _GREEN)
    _fill(pix, 24, 22, 220, 42, _WHITE)

    # three stat cards: Total Spend / Top Spender / Pending Settlements
    card_w, gap, top, bottom = 184, 20, 100, 230
    for i in range(3):
        x = 24 + i * (card_w + gap)
        _fill(pix, x - 1, top - 1, x + card_w + 1, bottom + 1, _BORDER)
        _fill(pix, x, top, x + card_w, bottom, _WHITE)
        _fill(pix, x, top, x + card_w, top + 8, _GREEN)          # accent strip
        _fill(pix, x + 16, top + 28, x + card_w - 60, top + 44, _TEXTBAR)   # label
        _fill(pix, x + 16, top + 64, x + card_w - 30, top + 96, _DARKBAR)   # big number

    # settlements list panel
    _fill(pix, 23, 259, W - 23, 371, _BORDER)
    _fill(pix, 24, 260, W - 24, 370, _WHITE)
    for i in range(3):
        y = 276 + i * 30
        _fill(pix, 40, y, 300, y + 14, _TEXTBAR)
        _fill(pix, W - 140, y, W - 48, y + 14, _GREEN)

    raw = b"".join(
        b"\x00" + b"".join(struct.pack("BBB", *px) for px in row) for row in pix)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
           + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)
    return path


# ------------------------------------------------------------------ WAV

def make_demo_wav(path: Path, seconds: float = 1.2, rate: int = 16000) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    n = int(seconds * rate)
    frames = bytearray()
    for i in range(n):
        t = i / rate
        # two soft chime tones with decay — a plausible 'voice note' stand-in
        amp = 0.35 * math.exp(-2.5 * t)
        sample = amp * (math.sin(2 * math.pi * 440 * t)
                        + 0.6 * math.sin(2 * math.pi * 660 * t))
        frames += struct.pack("<h", int(max(-1, min(1, sample)) * 32767))
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(bytes(frames))
    return path
