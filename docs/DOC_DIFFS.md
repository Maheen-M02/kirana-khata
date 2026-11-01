# Gnani docs vs `gnani-voice-api` skill: differences

Checked on **2026-11-01** against https://docs.gnani.ai/llms.txt and these pages:
`api/STT/speech-to-text`, `api/STT/models/prisma-v3`, `api/STT/limits`,
`api/TTS/tts-inference`, `api/TTS/tts-sse`, `api/TTS/available-voices`,
`api/TTS/tts-input-formating`, `api/introduction/errors` and `api/introduction/changelog`.

**Where the two disagree, the live docs win.** The `Action` column shows what the code will do.

## Confirmed (skill matches docs)

| Item | Value |
|---|---|
| STT endpoint | `POST https://api.vachana.ai/stt/v3`, multipart |
| STT audio field | **`audio_file`** (required) |
| STT model | `model=prisma-v3.0` (if omitted, v2.5 is used) |
| Auth header | `X-API-Key-ID` |
| STT formats / max length | WAV, MP3, OGG, FLAC, AAC, M4A; 30 s max |
| STT response | `success`, `request_id`, `transcript`, `model`, `detected_language_code`, `processing_time`, `end_to_end_latency` |
| TTS endpoints | `POST /api/v1/tts/inference` (raw bytes) and `POST /api/v1/tts/sse` |
| TTS body | `text`, `model`, `voice`, `language` (all required), `speed`, `audio_config{sample_rate,num_channels,sample_width,encoding,container,bitrate}` |
| TTS languages | `auto, hi-IN, en-IN, ta-IN, te-IN, kn-IN, ml-IN, mr-IN, pa-IN, bn-IN, gu-IN, hi-en`. `hi-en` is Hinglish. `"hinglish"` is rejected. |
| TTS speed | 0.85–1.15 (the docs add that the allowed range "depends on the model") |
| SSE events | `start`, `chunk{chunk_index, audio(b64), is_final}`, `complete` (`is_final:true`, empty audio), `error` |
| 429 | "Only 1 active request is allowed at a time", with **no `Retry-After` header** |

## Differences and additions

| # | Area | Skill says | Live docs say | Action |
|---|---|---|---|---|
| 1 | **Rate limit scope** | Single-flight queue for **TTS only** | The 1-active-request `429` is **per account** and is documented on the **STT** page as well as TTS | Use **one process-wide Gnani semaphore shared by STT and TTS** (`GNANI_MAX_CONCURRENCY=1`, configurable). Pre-warm the TTS cache at startup, not alongside live turns. Run a single backend instance in prod. Check the real limit on app.gnani.ai. |
| 2 | **STT `format` default on v3** | `format=transcribe` is optional | On v3, a single `hi-IN`/`en-IN` with no `format` returns **digits** (`transcribe`); everything else returns `verbatim` | **Always send `format` explicitly.** |
| 3 | **STT output styles** | `transcribe` only | `verbatim`, `transcribe`, `codemix` (v3) and **`transliterate`** (v3: the whole transcript in Latin letters, numbers as words, `language_code` optional, no `detected_language_code`) | In Phase 1/2, compare `transcribe` with `transliterate` on the golden set. `transliterate` suits the romanised rules parser and resolver. Make it configurable with `GNANI_STT_FORMAT`. |
| 4 | **STT `language_code`** | A single code or `indic-auto` | v3 also accepts **a comma-separated list of 1–4** codes (for example `hi-IN,en-IN`) as hints. Codes are case-sensitive (`hi-in` is rejected). | Default to `hi-IN,en-IN`, and add `mr-IN` when the Marathi toggle is on. The docs say listing languages "helps most with short clips". |
| 5 | **STT context hints** | Not mentioned | v3 accepts `keyterms` (≤200 words/phrases), `topic` (≤1600 chars), `previous_text` and `speaker_names` | Send the shop's customer names as `keyterms` and a short `topic` ("kirana shop udhaar hisaab"). Behind a flag; measure before and after. **Needs your OK** (it's an STT parameter, not a new feature). |
| 6 | **STT file type** | Not mentioned | The format is **detected from the file-name extension** | Always upload with `filename="audio.wav"`. |
| 7 | **STT short/long audio** | Reject <0.4 s and >28 s | <0.1 s returns `{"success":true,"transcript":""}` with no `model` or timings. An optional `truncated:true` flag means the token limit was hit. There is no `timestamp` on v3. | Keep the 0.4 s / 28 s guards. Treat `truncated` as low confidence. Make `model`/timings optional in the response model. |
| 8 | **Error body shapes** | `GnaniError(kind=auth\|rate_limit\|bad_audio\|upstream\|timeout)` | Five shapes: the STT envelope `{success:false,error:{type,message}}`; a `422 {"detail":[...]}`; auth/rate `{"detail":{error_code,message,status_code}}`; STT `504 {error,code:"UPSTREAM_TIMEOUT",message}` (5 s model limit); and TTS flat `{success:false,message,status_code}` | The parser handles all five. |
| 9 | **New error statuses** | none | **`402` insufficient credit**, `403 SCOPE_NOT_ALLOWED`, `400 EMPTY_AUDIO`, `INVALID_CONTEXT`, `MODEL_UNSUPPORTED_LANGUAGE` | Add `kind=credits` for 402 (friendly line plus a log alert). Map 403 to `auth` and the audio 400s to `bad_audio`. |
| 10 | **Retry policy** | Retry 429/5xx/network at most 2 times; TTS backoff 200/400/800 ms | Retry 429/500/503/504 and connection errors, 3 attempts, 0.5/1/2 s. `TRANSCRIPTION_FAILED` has already been retried once server-side. | Keep **at most 2 retries** (3 attempts, which matches the docs) with jittered backoff of 200/400/800 ms to stay inside the 3.5 s latency budget. Don't retry other 4xx. A TTS 500 can mean "text too long", so keep TTS strings short. |
| 11 | **TTS voice for Hinglish** | "Pick from catalog" | Timbre v2.5 voices each have **one preferred language**. **`Poorvi` is the only `hi-en` voice.** All 13 Timbre v3.0 voices speak every language (e.g. `Shivani`, `Avinash`). | Default `GNANI_TTS_VOICE=Poorvi` with `timbre-v2.5` + `hi-en`. Try `timbre-v3.0` + `Shivani` as the alternative in the Phase 1 smoke test. |
| 12 | **TTS number normalisation** | "Write numbers as words" | TTS now **normalises digits and ₹ automatically** on every request | Keep writing words with `numbers_hi.py`: it's deterministic and avoids English number words under `hi-en`/`auto`. No change. |
| 13 | **TTS audio defaults** | `sample_rate 24000`, mp3 64k | Default is 48000 Hz WAV. 24000 and mp3 `32k`–`192k` are supported. **OGG can't stream over SSE** (it arrives as one chunk). | Use mp3 at 24 kHz/64k for SSE and REST. Never use ogg. |
| 14 | **Official SDK** | Raw httpx | The `gnani-vachana` Python SDK exists on PyPI | Keep raw httpx so the shared semaphore, error mapping, credit guard and fakes stay under our control. No change. |
| 15 | Realtime STT (WS) | Headers `x-api-key-id`, `x-sample-rate` | For v3, the changelog adds `x-model`, `lang_code` and `x-format` | Not verified in detail; realtime is out of scope until the REST loop is solid. Re-fetch `api/STT/stt-websocket` before building it. |
