---
name: gnani-voice-api
description: Use when calling Gnani Prisma (speech-to-text) or Timbre (text-to-speech) APIs, handling audio formats, retries, rate limits or credit usage.
---

# Gnani voice APIs (Prisma STT and Timbre TTS)

These notes were checked against docs.gnani.ai in Nov 2026. **If anything fails or looks different, re-fetch https://docs.gnani.ai/llms.txt and the linked pages before changing code.**

## Basics

- Base URL: `https://api.vachana.ai` (WebSocket: `wss://api.vachana.ai`)
- Auth header: `X-API-Key-ID: <GNANI_API_KEY>` (keys come from app.gnani.ai)
- Errors reference: https://docs.gnani.ai/api/introduction/errors.md

## Prisma STT, REST (use this by default)

`POST /stt/v3` as multipart form:

- `audio_file`: the audio. Confirm the field name in docs/STT/speech-to-text.md.
- `language_code`: `hi-IN`, `mr-IN`, `en-IN` …, or `indic-auto` (v3.0 only)
- `model`: `prisma-v3.0`. If omitted, v2.5 is the default.
- `format=transcribe`: optional output style (numbers as digits). **Test both modes** against the golden set and keep whichever parses amounts better.

Constraints:

- Formats: WAV, MP3, OGG, FLAC, AAC, M4A. Sample rate 8–44.1 kHz. **Max 30 s.**
- Browsers record `webm/opus`, which is **not listed**. Always convert with ffmpeg first:
  `ffmpeg -i in.webm -ac 1 -ar 16000 -af silenceremove=start_periods=1:start_threshold=-45dB:stop_periods=1:stop_threshold=-45dB out.wav`
- Clamp clips to 28 s and reject anything under 0.4 s before calling (it saves credits).

The response contains `success`, `request_id`, `transcript`, `model`, and for v3 also `detected_language_code`, `processing_time` and `end_to_end_latency`. Store `request_id` on the `voice_event`.

## Prisma STT, realtime (optional, add later)

`wss://api.vachana.ai/stt/v3/stream`. Send headers `x-api-key-id` and `x-sample-rate: 16000`. Stream 16-bit mono PCM in 1024-byte frames, then send `{"type":"commit"}` to finish. Messages contain `type`, `text`, `segment_id` and `latency`. Only add this after the REST loop is solid; it's useful for live captions while the user talks.

## Timbre TTS

- REST: `POST /api/v1/tts/inference` returns raw audio bytes.
- SSE (preferred for latency): `POST /api/v1/tts/sse` sends `start`, `chunk{chunk_index, audio(base64), is_final}`, `complete` and `error` events.

Request body:

```json
{"text": "Sharma ji, ek sau bees rupaye udhaar. Sahi hai?",
 "model": "timbre-v2.5", "voice": "<from catalog>", "language": "hi-en",
 "speed": 1.0,
 "audio_config": {"sample_rate": 24000, "num_channels": 1, "sample_width": 2,
                  "encoding": "linear_pcm", "container": "mp3", "bitrate": "64k"}}
```

- Languages: `auto, hi-IN, en-IN, ta-IN, te-IN, kn-IN, ml-IN, mr-IN, pa-IN, bn-IN, gu-IN, hi-en`. Use **`hi-en` for Hinglish**.
- Voices are **model-specific**. v2.5 has 42 voices, each with a preferred language. v3.0 has 13 voices that cover all languages and support tags like `<pauses>`. See https://docs.gnani.ai/api/TTS/available-voices.md. Make the voice configurable and pick a warm, clear voice for the demo.
- **Write numbers as words** ("ek sau bees rupaye", not "₹120"). Use `nlu/numbers_hi.py` to convert them.
- Speed range is 0.85–1.15. Use 0.95 for older shopkeepers.
- **429 means only 1 active request is allowed at a time.** Every TTS call must therefore go through a process-wide `asyncio.Semaphore(1)` queue (`voice/tts_queue.py`). Retry 429 with jittered backoff of 200 ms, 400 ms, then 800 ms.
- Cache the audio keyed on sha256(text + voice + model + config) on disk or in object storage. Pre-warm common phrases like "Samajh nahi aaya, dobara boliye", "Entry ho gayi", "Theek hai, cancel kar diya" and "Haan ya nahi boliye".

## Client implementation rules

- Use a single shared `httpx.AsyncClient`, with a 10 s timeout for STT and 15 s for TTS.
- Retry only on 429, 5xx and network errors, at most 2 times. Never retry a 400 or 403.
- Map errors to `GnaniError(kind=auth|rate_limit|bad_audio|upstream|timeout)`. The UI shows a friendly Hinglish line for each kind.
- Log the endpoint, status, latency and request_id. **Never log the key or raw audio bytes.**
- Credit guard: keep a counter in the DB, and once it passes `GNANI_CREDIT_GUARD` in dev, raise before calling.
- Provide `FakeSTT` and `FakeTTS` implementations, with transcripts keyed by fixture filename, for tests.
