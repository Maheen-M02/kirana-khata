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

| Stage | Measured |
|---|---|
| ffmpeg prep | ~120 ms for a 2.8 s webm clip (local, Windows) |
| Prisma STT | not measured yet: needs the live smoke run |
| NLU | Phase 2 |
| Timbre time to first chunk (SSE) | not measured yet: needs the live smoke run |
