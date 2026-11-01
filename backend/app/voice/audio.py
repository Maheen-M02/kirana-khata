"""Audio prep: any browser recording -> 16 kHz mono 16-bit WAV, edge silence trimmed,
duration-checked *before* any billable call.

Why temp files instead of pipes: iOS Safari records audio/mp4, whose `moov` atom can sit at the
end of the file; ffmpeg cannot demux that from a non-seekable pipe. WAV written to a pipe also
gets an unknown-length header. Clips are tiny, so temp files cost ~nothing.

Why not the skill's `silenceremove ... stop_periods=1`: that stops output at the *first* pause
after speech, which would cut "Sharma ji ne... [pause] ...udhaar" short. We trim the start,
reverse, trim the start again, and reverse back: only leading/trailing silence is removed.
"""

from __future__ import annotations

import asyncio
import io
import shutil
import subprocess
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

MIN_DURATION_S = 0.4
MAX_DURATION_S = 28.0
SAMPLE_RATE = 16_000
_SILENCE_DB = "-45dB"
_KEEP_PAD_S = 0.15  # keep a little silence so the first/last phoneme isn't clipped


def _edge_trim(pad_s: float) -> str:
    t = f"silenceremove=start_periods=1:start_threshold={_SILENCE_DB}:start_silence={pad_s}"
    return f"{t},areverse,{t},areverse"


# One decode, two outputs: [stt] keeps small pads and is what we upload; [speech] has no pads
# and is only measured, so a 0.3 s tap can't sneak past MIN_DURATION_S thanks to padding.
FILTER_GRAPH = (
    f"[0:a]aformat=sample_fmts=s16:sample_rates={SAMPLE_RATE}:channel_layouts=mono,asplit=2[a][b];"
    f"[a]{_edge_trim(_KEEP_PAD_S)}[stt];[b]{_edge_trim(0)}[speech]"
)
_FFMPEG_TIMEOUT_S = 15
_MAX_INPUT_S = 60  # never decode more than this, whatever was uploaded

RejectReason = Literal["too_short", "too_long", "undecodable", "no_ffmpeg"]

REJECT_MESSAGES: dict[RejectReason, str] = {
    "too_short": "Bahut chhota tha. Button dabaye rakhiye aur poora boliye.",
    "too_long": "Thoda chhota boliye, 25 second se kam.",
    "undecodable": "Awaaz samajh nahi aayi, dobara boliye.",
    "no_ffmpeg": "Kuch gadbad ho gayi. Thodi der baad koshish kijiye.",
}


class AudioError(Exception):
    def __init__(self, reason: RejectReason, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason: RejectReason = reason
        self.detail = detail

    @property
    def user_message(self) -> str:
        return REJECT_MESSAGES[self.reason]


@dataclass(frozen=True)
class PreparedAudio:
    wav: bytes
    duration_ms: int  # what we upload (speech + small pads)
    speech_ms: int  # leading/trailing silence fully removed
    input_bytes: int


def wav_duration_ms(wav_bytes: bytes) -> int:
    with wave.open(io.BytesIO(wav_bytes), "rb") as w:
        frames, rate = w.getnframes(), w.getframerate()
    return round(frames * 1000 / rate) if rate else 0


def check_duration(*, speech_ms: int, upload_ms: int) -> None:
    if speech_ms < MIN_DURATION_S * 1000:
        raise AudioError("too_short", f"{speech_ms} ms of speech")
    if upload_ms > MAX_DURATION_S * 1000:
        raise AudioError("too_long", f"{upload_ms} ms")


def _convert_sync(data: bytes, ffmpeg: str) -> tuple[bytes, bytes]:
    with tempfile.TemporaryDirectory(prefix="kk-audio-") as tmp:
        src = Path(tmp) / "in"
        stt_out, speech_out = Path(tmp) / "stt.wav", Path(tmp) / "speech.wav"
        src.write_bytes(data)
        cmd = [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
            "-t", str(_MAX_INPUT_S), "-i", str(src), "-filter_complex", FILTER_GRAPH,
            "-map", "[stt]", "-c:a", "pcm_s16le", str(stt_out),
            "-map", "[speech]", "-c:a", "pcm_s16le", str(speech_out),
        ]  # fmt: skip
        try:
            proc = subprocess.run(  # noqa: S603  (fixed argv, no shell)
                cmd, capture_output=True, timeout=_FFMPEG_TIMEOUT_S, check=False
            )
        except subprocess.TimeoutExpired as e:
            raise AudioError("undecodable", "ffmpeg timeout") from e
        if proc.returncode != 0 or not stt_out.exists() or not speech_out.exists():
            stderr = proc.stderr.decode("utf-8", "replace").strip().splitlines()
            raise AudioError("undecodable", stderr[-1][:200] if stderr else "ffmpeg failed")
        return stt_out.read_bytes(), speech_out.read_bytes()


async def prepare_audio(data: bytes, *, ffmpeg: str | None = None) -> PreparedAudio:
    """Convert + trim + validate. Raises AudioError; never spends Gnani credits."""
    if not data:
        raise AudioError("too_short", "empty upload")
    exe = ffmpeg or shutil.which("ffmpeg")
    if not exe:
        raise AudioError("no_ffmpeg", "ffmpeg not found on PATH")
    # Thread, not asyncio subprocess: works under every event loop (incl. uvicorn on Windows).
    wav, speech = await asyncio.to_thread(_convert_sync, data, exe)
    try:
        upload_ms, speech_ms = wav_duration_ms(wav), wav_duration_ms(speech)
    except (wave.Error, EOFError) as e:
        raise AudioError("undecodable", "bad wav output") from e
    check_duration(speech_ms=speech_ms, upload_ms=upload_ms)
    return PreparedAudio(wav=wav, duration_ms=upload_ms, speech_ms=speech_ms, input_bytes=len(data))
