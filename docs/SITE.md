# Marketing site (`site/`)

A one-page site for **kirana shopkeepers**: Hinglish first, short sentences, every claim true of the app today. It's a separate Next.js 14 app exported to static HTML (`site/out`), so any CDN can serve it (a Vercel project with the root directory set to `site/`). It has no backend and no tracking.

| Section | Job |
|---|---|
| Hero (ink) | The promise, "Bolo, aur hisaab likh jayega.", plus a **playable real exchange** |
| Jaise grahak se baat karte hain… | Six things you can say, laid out as a khata page; each reply is the app's real template text |
| Teen kadam | The loop: press and speak → it repeats "Sahi hai?" → "haan" writes it (numbered because it is a sequence) |
| Hisaab aapka, faisla bhi aapka | Trust: the haan gate, cancel entries instead of edits, "Kaun se Sharma ji?", the ₹50,000 double confirmation, the PIN lockout |
| Phone par app ki tarah lagaiye | Add-to-home-screen steps for the PWA |
| Aapke sawaal | FAQ: internet, mishearing, noise, language, privacy |

- **Demo audio:** `public/audio/*.mp3` are two Timbre (Shivani, timbre-v3.0) clips the app spoke during the first live test on 2026-11-01. They were matched to their text by recomputing the TTS cache key `sha256("timbre-v3.0|Shivani|hi-en|<text>")`, so no new credits were spent. The shopkeeper line is Prisma's actual transcript from that test.
- **Config:** `NEXT_PUBLIC_APP_URL` (build time) points "Khata kholiye" and "Login" at `<app>/login`. The default is `http://localhost:3000`.
- **Design:** the same tokens and font as the app (see [FRONTEND.md](FRONTEND.md#visual-design)). The demo is the page's one moving part.
- **Deliberately absent:** pricing, sign-up, and Marathi. There's no self-serve sign-up yet; shops are created with `make seed` or `make set-pin`.
- **Commands:** `make site-dev` (:3001), `make site-build`, `make lint-site`. CI builds the site and checks that the export contains the page and both clips.
