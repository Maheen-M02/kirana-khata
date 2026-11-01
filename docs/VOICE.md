# Voice layer (Phase 1)

`backend/app/voice/`. The rest of the app talks only to the `SpeechToText` and `TextToSpeech` protocols. Tests use `FakeSTT` and `FakeTTS`.

| Module | Job |
|---|---|
| `audio.py` | Converts any browser recording (webm/opus, Safari mp4/aac, wav…) to a 16 kHz mono s16 WAV with the edges trimmed. **Rejects** clips with under 0.4 s of speech or over 28 s uploaded, before any credits are spent. Uses temp files, not pipes, because of Safari's trailing `moov` atom. |
| `gnani_http.py` | `GnaniTransport` handles the `X-API-Key-ID` header, the credit guard, the single-flight gate, and retries (429, 5xx, network and timeouts; at most 2 retries, jittered backoff of 200/400 ms). It logs endpoint, status, latency and request_id, and **never the key or audio**. |
| `tts_queue.py` | `SingleFlight`: one Gnani request at a time across **STT and TTS** (the account-wide limit; DOC_DIFFS #1). SSE holds the slot until the stream finishes. |
| `credit_guard.py` | `FileCreditGuard` keeps a per-day (IST) counter in `var/gnani_credits.json`. It refuses calls past `GNANI_CREDIT_GUARD` in dev; in other environments it counts and logs only. |
| `errors.py` | `GnaniError(kind=auth\|credits\|rate_limit\|bad_audio\|bad_request\|upstream\|timeout\|budget)` parsed from all 5 documented body shapes, each with a short Hinglish `user_message`. |
| `gnani_stt.py` | `GnaniSTT` calls `POST /stt/v3` with the `audio_file` field and `filename=audio.wav` (the format is detected from the extension). It always sends `format`, sends `keyterms` when given, and handles `truncated`. |
| `gnani_tts.py` | `GnaniTTS` supports REST `synthesize()` and SSE `stream()` (mp3, 24 kHz, 64k), with a sha256 disk cache in `var/tts_cache/`. `PREWARM_PHRASES` gets warmed at startup from Phase 4. |
| `factory.py` | `build_voice(settings)` builds one shared `httpx.AsyncClient`, gate and guard. |

## Commands (spend credits; only when asked)

```bash
make smoke-voice FILE=clip.webm                      # prep -> STT -> TTS(SSE) "Aapne kaha: ..." (2 calls)
make smoke-voice FILE=clip.webm ARGS="--no-tts --format transliterate --record"
make tts-say TEXT="Entry ho gayi." ARGS="--model timbre-v3.0 --voice Shivani"
make test-live                                       # Timbre -> ffmpeg -> Prisma round trip (2 calls)
```

`--record` saves the STT response to `tests/fixtures/gnani/*.recorded.json` for replay tests.

## Latency budget (target ≤ 3.5 s p50, mic release to first audio)

These are first live measurements from 2026-11-01: single runs from a home connection in India, not a p50. Proper p50/p95 numbers come from `/debug` in Phase 7.

| Stage | Measured |
|---|---|
| ffmpeg prep | 120–122 ms (2.8–3.6 s clips) |
| Prisma STT v3 (round trip from client) | 518 / 587 / 637 ms; upstream `processing_time` 0.42 s |
| NLU | Phase 2 (Evon has a 4 s timeout; rules is about 1 ms) |
| Timbre time to first chunk over SSE | 368 ms (v2.5 Poorvi), 308 ms (v3.0 Shivani) |
| **Subtotal without NLU or upload** | **about 1.0–1.1 s**: leaves about 2.4 s for upload and NLU |

## What Prisma actually returns (recorded)

For TTS audio of *"Sharma ji ne do kilo cheeni li, ek sau bees rupaye udhaar."*, `format=transcribe` with `hi-IN,en-IN` returned:

```
शर्मा जी ने 2 kg चीनी ली, 120 रुपये उधार।
```

- Numbers and units come back as **digits** ("120", "2 kg"), so the hard Hindi-number parsing is mostly needed for `verbatim`/`transliterate` output or fallback.
- Hindi words come back in **Devanagari**, so the rules parser and customer resolver must handle Devanagari keywords (उधार, जमा) and transliterate names. Phase 2 will compare against `format=transliterate` (1 credit).

## Voice A/B (Timbre)

| Option | First chunk | Audio length | File |
|---|---|---|---|
| `timbre-v2.5` + `Poorvi` + `hi-en` | 368 ms | 3.6 s | `backend/var/smoke/ab_poorvi_v25.mp3` |
| **`timbre-v3.0` + `Shivani` + `hi-en` (chosen, now the default)** | 308 ms | 4.1 s | `backend/var/smoke/ab_shivani_v30.mp3` |

The owner picked Shivani by ear on 2026-11-01. Change it with `GNANI_TTS_MODEL` / `GNANI_TTS_VOICE`.

`transliterate` A/B (1 credit, same clip): `Sharma ji ne do kilo chini li, ek sau bees rupaye udhar.` (592 ms, no `detected_language_code`). `transcribe` stays the default (see ARCHITECTURE decisions).
