"""Real ffmpeg (installed locally and in CI): conversion, trimming and duration guards."""

from __future__ import annotations

import shutil
import subprocess
import wave
from io import BytesIO
from pathlib import Path

import pytest

from app.voice.audio import AudioError, PreparedAudio, prepare_audio

FFMPEG = shutil.which("ffmpeg")
pytestmark = pytest.mark.skipif(FFMPEG is None, reason="ffmpeg not installed")


def synth(
    tmp: Path, parts: list[tuple[str, float]], codec: str = "libopus", ext: str = "webm"
) -> bytes:
    """parts: [("tone"|"silence", seconds)] -> encoded bytes, like a browser recording."""
    assert FFMPEG
    args: list[str] = [FFMPEG, "-hide_banner", "-loglevel", "error", "-y"]
    for i, (kind, dur) in enumerate(parts):
        src = (
            f"sine=f={440 + 110 * i}:r=48000:d={dur}"
            if kind == "tone"
            else f"anullsrc=r=48000:cl=mono:d={dur}"
        )
        args += ["-f", "lavfi", "-i", src]
    n = len(parts)
    args += ["-filter_complex", "".join(f"[{i}]" for i in range(n)) + f"concat=n={n}:v=0:a=1"]
    out = tmp / f"clip.{ext}"
    args += ["-c:a", codec, str(out)]
    subprocess.run(args, check=True)  # noqa: S603
    return out.read_bytes()


def assert_16k_mono(p: PreparedAudio) -> None:
    with wave.open(BytesIO(p.wav)) as w:
        assert (w.getframerate(), w.getnchannels(), w.getsampwidth()) == (16000, 1, 2)


async def test_webm_opus_converted_and_edges_trimmed(tmp_path: Path) -> None:
    data = synth(tmp_path, [("silence", 1.0), ("tone", 1.0), ("silence", 1.5)])
    p = await prepare_audio(data)
    assert_16k_mono(p)
    assert 1000 <= p.duration_ms <= 1500  # 1 s tone + small pads, not 3.5 s
    assert 900 <= p.speech_ms <= 1100  # pads excluded from the speech measurement
    assert p.input_bytes == len(data)


async def test_mid_sentence_pause_is_kept(tmp_path: Path) -> None:
    """Regression for the skill's `stop_periods=1` filter, which cut output at the first pause."""
    data = synth(
        tmp_path,
        [("silence", 0.5), ("tone", 0.5), ("silence", 0.6), ("tone", 0.5), ("silence", 0.7)],
    )
    p = await prepare_audio(data)
    assert p.duration_ms >= 1550  # both words + the pause survive


async def test_mp4_aac_from_safari_works(tmp_path: Path) -> None:
    data = synth(tmp_path, [("tone", 1.0)], codec="aac", ext="m4a")
    assert_16k_mono(await prepare_audio(data))


async def test_accidental_tap_rejected_before_any_credits(tmp_path: Path) -> None:
    # QA checklist: "a 0.3 s accidental tap". Padding must not push it past the 0.4 s floor.
    data = synth(tmp_path, [("silence", 0.5), ("tone", 0.3), ("silence", 0.5)])
    with pytest.raises(AudioError) as ei:
        await prepare_audio(data)
    assert ei.value.reason == "too_short"


async def test_silence_only_rejected(tmp_path: Path) -> None:
    with pytest.raises(AudioError) as ei:
        await prepare_audio(synth(tmp_path, [("silence", 2.0)]))
    assert ei.value.reason == "too_short"


async def test_over_28s_rejected(tmp_path: Path) -> None:
    with pytest.raises(AudioError) as ei:
        await prepare_audio(synth(tmp_path, [("tone", 29.0)]))
    assert ei.value.reason == "too_long"


async def test_garbage_bytes_are_undecodable() -> None:
    with pytest.raises(AudioError) as ei:
        await prepare_audio(b"this is not audio at all" * 50)
    assert ei.value.reason == "undecodable"
    assert ei.value.user_message


async def test_empty_upload_rejected() -> None:
    with pytest.raises(AudioError):
        await prepare_audio(b"")
