"""Live Gnani round trip — SPENDS CREDITS (1 STT + 1 TTS per run; TTS is free on a cache hit).

    make smoke-voice FILE=clip.webm                        # STT then TTS (SSE)
    make smoke-voice FILE=clip.webm ARGS="--format transliterate --record"
    make tts-say TEXT="Entry ho gayi." ARGS="--model timbre-v3.0 --voice Shivani"

Phase 1 stops at transcript -> speech. The NLU step is wired in Phase 2.
Respects GNANI_CREDIT_GUARD. Never prints the API key.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from app.config import Settings, get_settings
from app.core.logging import configure_logging
from app.voice.audio import AudioError, prepare_audio
from app.voice.errors import GnaniError
from app.voice.factory import VoiceStack, build_voice
from app.voice.gnani_stt import SttResult

DEFAULT_SAY = "Theek hai. Sharma ji, ek sau bees rupaye udhaar. Sahi hai?"
BACKEND = Path(__file__).resolve().parents[1]
FIXTURES = BACKEND / "tests" / "fixtures" / "gnani"


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")[:40] or "clip"


def _mp3_seconds(path: Path) -> float | None:
    probe = shutil.which("ffprobe")
    if not probe:
        return None
    out = subprocess.run(  # noqa: S603
        [probe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=False,
    )  # fmt: skip
    try:
        return float(out.stdout.strip())
    except ValueError:
        return None


def _record(stem: str, fmt: str, r: SttResult) -> Path:
    body = {
        "success": True,
        "request_id": r.request_id,
        "transcript": r.transcript,
        "model": r.model,
        "detected_language_code": r.detected_language,
        "processing_time": r.upstream_processing_s,
        "end_to_end_latency": r.upstream_e2e_s,
    }
    if r.truncated:
        body["truncated"] = True
    path = FIXTURES / f"stt_{_slug(stem)}.{fmt}.recorded.json"
    path.write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


async def _stt(stack: VoiceStack, file: Path, record: bool) -> SttResult:
    raw = file.read_bytes()
    t0 = time.perf_counter()
    audio = await prepare_audio(raw)
    prep_ms = round((time.perf_counter() - t0) * 1000)
    print(f"audio   : {file.name}  {len(raw)} B -> {audio.duration_ms} ms wav "
          f"({audio.speech_ms} ms speech), prep {prep_ms} ms")  # fmt: skip
    r = await stack.stt.transcribe(audio.wav, filename="audio.wav")
    print(f"stt     : [{stack.stt.model} / {stack.stt.language} / format={stack.stt.fmt}]")
    print(f"          transcript = {r.transcript!r}")
    print(f"          lang={r.detected_language} truncated={r.truncated} request_id={r.request_id}")
    print(f"          latency {r.latency_ms} ms (upstream processing {r.upstream_processing_s}s, "
          f"e2e {r.upstream_e2e_s}s)")  # fmt: skip
    if record:
        print(f"          recorded -> {_record(file.stem, stack.stt.fmt, r).relative_to(BACKEND)}")
    return r


async def _tts(stack: VoiceStack, text: str, out: Path) -> None:
    t0 = time.perf_counter()
    first_ms: int | None = None
    chunks: list[bytes] = []
    async for chunk in stack.tts.stream(text):
        if first_ms is None:
            first_ms = round((time.perf_counter() - t0) * 1000)
        chunks.append(chunk)
    total_ms = round((time.perf_counter() - t0) * 1000)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(b"".join(chunks))
    secs = _mp3_seconds(out)
    print(f"tts     : [{stack.tts.model} / {stack.tts.voice} / {stack.tts.language}] {text!r}")
    print(f"          first audio {first_ms} ms, total {total_ms} ms, {len(chunks)} chunk(s), "
          f"{out.stat().st_size} B, {secs if secs is not None else '?'} s audio")  # fmt: skip
    print(f"          saved -> {out}")


async def run(args: argparse.Namespace, settings: Settings) -> int:
    overrides: dict[str, object] = {}
    if args.format:
        overrides["gnani_stt_format"] = args.format
    if args.language:
        overrides["gnani_stt_language"] = args.language
    if args.model:
        overrides["gnani_tts_model"] = args.model
    if args.voice:
        overrides["gnani_tts_voice"] = args.voice
    if overrides:
        settings = Settings.model_validate({**settings.model_dump(), **overrides})

    stack = build_voice(settings)
    smoke_dir = settings.var_dir / "smoke"
    try:
        say = args.say
        if args.file:
            r = await _stt(stack, Path(args.file), args.record)
            if not say:
                say = DEFAULT_SAY if r.is_empty else f"Aapne kaha: {r.transcript}"
        if not args.no_tts:
            label = _slug(Path(args.file).stem if args.file else (say or "say"))
            await _tts(stack, say or DEFAULT_SAY, smoke_dir / f"{label}.mp3")
    finally:
        await stack.aclose()
        print(f"credits : {stack.guard.used_today()} billable Gnani calls today "
              f"(guard {stack.guard.limit or 'off'})")  # fmt: skip
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("file", nargs="?", help="audio clip (webm/m4a/wav/mp3...)")
    p.add_argument("--say", help="text for TTS (spoken-form numbers!)")
    p.add_argument("--no-tts", action="store_true", help="STT only")
    p.add_argument("--record", action="store_true", help="save STT response as a test fixture")
    p.add_argument("--format", choices=["verbatim", "transcribe", "codemix", "transliterate"])
    p.add_argument("--language", help="override GNANI_STT_LANGUAGE, e.g. hi-IN or indic-auto")
    p.add_argument("--model", help="override GNANI_TTS_MODEL, e.g. timbre-v3.0")
    p.add_argument("--voice", help="override GNANI_TTS_VOICE (must belong to the TTS model)")
    args = p.parse_args(argv)
    if not args.file and not args.say:
        p.error("give an audio FILE and/or --say TEXT")

    configure_logging(json_logs=False)
    settings = get_settings()
    if not settings.gnani_configured:
        print("GNANI_API_KEY is empty — add it to .env (never commit it).", file=sys.stderr)
        return 2
    try:
        return asyncio.run(run(args, settings))
    except AudioError as e:
        print(f"audio rejected ({e.reason}): {e.detail}\n  user would hear: {e.user_message}")
        return 1
    except GnaniError as e:
        print(f"gnani error kind={e.kind} status={e.status} code={e.code}: {e.detail}")
        print(f"  user would hear: {e.user_message}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
