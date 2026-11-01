# Frontend (Phase 5, redesigned after Phase 6)

The frontend is a Next.js 14 (App Router) PWA with Tailwind and shadcn. **Everything is a server component except the voice console** (`components/voice-console.tsx`) and the service-worker registration.

| Screen | Route | Shows |
|---|---|---|
| Bolo (home) | `/` | The big hold-to-talk mic, the confirm card, today's sales and entries |
| Khate | `/customers` | Every customer with their balance, biggest dues first, and the total outstanding |
| Customer | `/customers/[id]` | The balance (baaki / advance / barabar) and full history; cancelled entries are struck through |

## Visual design

The look is a shopkeeper's khata: blue ballpoint on ruled paper, with one marigold action.

| Token | Hex | Used for |
|---|---|---|
| `ink` | #1B2559 | Text, headers, totals panels |
| `marigold` | #F5A400 | The mic button and the login button only |
| `paper` | #FAFAF7 | Background |
| `udhaar` | #C0262D | Money owed (red ink) |
| `jama` | #13795B | Money received, the Haan button |
| `rule` / `margin` | #DCE1EC / #E8A9AC | Ledger lines and the red double margin before the amount column |

- **Type:** Anek Devanagari, one variable family for both Latin and Devanagari names. Its width axis sets money figures condensed and heavy (`.w-condensed`) and the wordmark wide (`.w-wide`).
- **Tokens:** defined in `app/globals.css` as bare HSL triplets and wrapped in `tailwind.config.ts` as `hsl(var(--x) / <alpha-value>)`. Before the redesign the CSS held `oklch()` values that the config wrapped in `hsl()`; browsers rejected those, so every themed colour silently fell back to the default.
- **Lists:** entry and customer lists are drawn as a khata page (`.ledger-margin`), with amounts in a fixed 7.5rem column right of the red margin.
- **Mic:** marigold at rest, ink with a marigold ring while listening. The ring scales with the live input level (Web Audio `AnalyserNode`), so the shopkeeper can see it hears them in a noisy shop. Reduced motion is respected.
- **Login:** an ink brand panel with a sample exchange (what you say, what the khata answers), a +91 phone field, and 4 PIN boxes over one real input. It submits on the fourth digit and clears and refocuses the PIN after an error.

## Voice console

- **State machine:** `lib/voice-machine.ts` is a pure reducer (idle → listening → thinking → speaking → awaiting), so its states and edge cases are unit-tested.
- **Hold to talk:** pointer events with pointer capture; Space/Enter also work, for keyboard and accessibility. Clips under 400 ms are never sent (no credits spent), and recording auto-stops at 25 s.
- **Recording format:** `MediaRecorder` with Opus/webm, or mp4 on Safari. Echo cancellation and noise suppression are on, and the mic light turns off between turns.
- **Answering a question:** while one is open (✓/✗, which Sharma, how much), the next recording goes to `/voice/{id}/confirm`. Taps send JSON.
- **Playback:** Timbre audio plays from the cached `confirm_audio_url`. Talking stops playback (barge-in). The text is always shown, even when there's no audio.
- **Refresh:** after a commit, `router.refresh()` re-renders the server-side ledger views.
- **Money in the browser:** integer paise only (`rupeesToPaise`, `formatInr`). The UI never does arithmetic on floating-point rupees.

## PWA

The manifest has 192 and 512 icons (`any` + `maskable`) plus an Apple touch icon. `public/sw.js` follows these rules:

| Request | Strategy |
|---|---|
| App shell, `offline.html` | Cached on install |
| `/_next/static`, `/icons`, `/api/voice/audio/*` | Cache-first (all immutable) |
| Page navigation | Network-first, falling back to the offline page |
| `/api/*` | **Never cached** (balances must not be stale) |

Security headers are set too: `Permissions-Policy: microphone=(self)`, `nosniff` and `Referrer-Policy`.

## Measured (local production build, seeded demo shop, Lighthouse 12.8 mobile)

| Page | Performance | Accessibility | Best practices |
|---|---|---|---|
| `/` | 100 | 100 | 100 |
| `/customers` | 100 | 100 | 100 |

After the redesign (dev server, Lighthouse 12.8.2 mobile, logged in): Accessibility **100** on `/login`, `/`, `/customers` and `/customers/1`; Best practices 100 on `/login`. Performance hasn't been re-measured on a production build yet.

**Lighthouse 12 removed the PWA category**, so the spec's "PWA ≥ 90" can't be scored. Installability was checked directly: manifest fields, icon sizes and purposes, service worker headers and scope, offline page. **Android Chrome over HTTPS** gets tested after the Phase 7 deploy.

## Tests

35 vitest tests:
- the state machine and money helpers;
- **component tests that drive the real `VoiceConsole`** with a fake `MediaRecorder` and microphone: hold → send (with the idempotency key) → confirm → Haan → refresh; plus a 0.2 s tap (no request), mic denied, disambiguation taps, and friendly server errors.
