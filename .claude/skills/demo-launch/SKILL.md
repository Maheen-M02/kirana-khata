---
name: demo-launch
description: Use when writing the README, architecture docs, the 60-second demo script, or LinkedIn/X launch posts for the Gnani AI internship challenge submission.
---

# Demo and launch kit

Selection depends on **public engagement** on LinkedIn or X, followed by an interview. The demo has to hook people in the first 3 seconds and still hold up to technical scrutiny in the interview.

## README.md structure

1. A one-line pitch and a 10-second GIF of a voice turn
2. "Built on Gnani AI": a table mapping Prisma, Timbre and Evon to where each is used
3. Architecture diagram (Mermaid): phone PWA → FastAPI → Prisma STT → Evon plus rules NLU → ledger DB → Timbre TTS
4. Measured results: golden-set accuracy by tag, p50/p95 latency, and noisy-audio results
5. Design decisions: an append-only ledger, money in paise, mandatory confirmation, LLM output cross-checked by rules, and the TTS single-flight queue
6. Running locally, deployment and env vars
7. Roadmap: phone-call channel (IVR), credit scoring from udhaar history, and multi-shop support

## 60-second demo script (`docs/DEMO_SCRIPT.md`)

| Time | Shot | Audio and caption |
|---|---|---|
| 0–3 s | A real shop and the shopkeeper's face | "Ramesh uncle ne kabhi type nahi kiya. Ab woh bolke hisaab rakhte hain." |
| 3–15 s | He holds the mic: "Sharma ji ne do kilo cheeni, ek sau bees udhaar" | Timbre confirms, he says "haan", and the balance is spoken |
| 15–25 s | A payment: "Gupta ji ne 300 jama kiye" | The balance updates on screen |
| 25–35 s | A query: "Kis kis ka paisa baaki hai?" | Spoken top 3 |
| 35–45 s | A noisy moment (traffic or a pressure cooker) where it still works | Caption: "Noisy shop? No problem." |
| 45–55 s | A quick architecture overlay with Prisma, Evon and Timbre, plus the latency number | |
| 55–60 s | "Kirana Khata — built on Gnani AI." | Hashtags and the link |

Shoot it vertically (9:16), burn in subtitles in both Hindi and English, show real audio, and **don't fake anything**. Record 3 takes and keep the best.

## Posting

- Post on LinkedIn and X, natively uploaded (not YouTube links). Use **#GnaniAI #GreatIndianAIInternshipChallenge** and tag Gnani AI.
- Post on a weekday morning, between 9 and 11 am IST. Reply to every comment within the first 2 hours.
- Draft 3 hooks and A/B them with friends first.
- Make the first comment the GitHub and live-demo links plus a technical thread (architecture, accuracy and latency numbers).
- Share the post in college groups, with local kirana owners and in developer communities. Ask for genuine feedback, not just likes.
- Prepare a short technical write-up post for 2 days later, such as "How I made a 30B LLM safe for money" (Evon plus rules plus confirmation).

## Interview prep notes (generate `docs/INTERVIEW_NOTES.md`)

Cover:

- why this problem
- STT failure modes seen and how you fixed them
- the latency budget breakdown
- why not just the LLM alone
- how to scale to a phone-call channel using Gnani telephony formats (mulaw at 8 kHz)
- what you'd build next
