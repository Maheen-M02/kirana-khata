---
name: evon-llm
description: Use when hosting, calling or prompting Gnani Evon (gnani-evon-v3.3-30B-A3B), the reasoning LLM used to turn Hinglish transcripts into structured ledger intents.
---

# Gnani Evon LLM

- **Model:** `gnani/gnani-evon-v3.3-30B-A3B` on Hugging Face (Apache-2.0). It is a mixture-of-experts model with 30B total parameters and about 3.5B active, and a 128K context.
- **No public hosted API is listed.** You must serve it yourself behind an **OpenAI-compatible** `/v1/chat/completions` endpoint.

## Hosting options (pick one and record it in docs/ARCHITECTURE.md)

1. **GPU vLLM (best quality and latency)** on Modal, RunPod or a Lightning/Kaggle GPU (A100 or H100 class):

   ```
   pip install -U "vllm>=0.12.0"
   vllm serve gnani/gnani-evon-v3.3-30B-A3B --trust-remote-code --max-model-len 16384 \
     --enable-auto-tool-choice --tool-call-parser qwen3_coder --reasoning-parser nano_v3 \
     --served-model-name evon --api-key $EVON_API_KEY
   ```

   A short `--max-model-len` (for example 16384) saves memory, since the prompts here are short. Scale to zero when idle to save money, and **warm it up before filming**.
2. **Quantized GGUF via Ollama or llama.cpp** on a laptop or cheap VM. A Q4 build needs roughly 20 GB of RAM or VRAM. It's slower but free. Run `llama-server --port 8080`, which also exposes `/v1/chat/completions`.
3. **SGLang**, which exposes the same OpenAI API on port 30000.

Check the HF model card for exact flags if a command fails; don't guess.

## Calling it

Point the OpenAI-compatible client at `EVON_BASE_URL` with `EVON_MODEL` and `EVON_API_KEY`:

- `temperature 0.2` for extraction (the model card suggests 0.6 / top_p 0.95 for chat; extraction should be near-deterministic), `max_tokens 400`.
- **Turn thinking off** for latency with `extra_body={"chat_template_kwargs": {"enable_thinking": False}}`.
- Structured output isn't documented. Get JSON this way:
  1. The system prompt says to return **only** JSON matching the schema, with no prose or markdown.
  2. Strip any `<think>…</think>` block and code fences, then extract the first `{…}` object.
  3. Validate with Pydantic (`nlu/schema.py`). If validation fails, retry once with the validation error included in the prompt.
  4. If it still fails or times out after 4 s, use the rules parser (`nlu/rules.py`) and set `nlu_source="rules"` and lower confidence.
  5. If vLLM's `guided_json` / `response_format` works on your build, enable it behind a flag.

## Prompt skeleton (`nlu/prompts.py`)

```
System: You are the parser for a kirana shop ledger. Input: one transcript (Hinglish/Hindi/Marathi, may contain STT errors).
Output ONLY JSON: {"intent": one of [credit_sale, cash_sale, payment_received, query_balance,
 query_sales_today, query_dues_list, undo_last, confirm_yes, confirm_no, unknown],
 "customer": string|null, "items": [{"name","qty","unit"}], "amount_rupees": number|null,
 "amount_text": string|null, "confidence": 0..1}
Rules: "udhaar/baaki/khate mein" -> credit_sale. "jama/diye/de gaye/payment" -> payment_received.
"nakad/cash" or no customer -> cash_sale. Never invent amounts; if unsure set null and confidence<0.6.
Copy the spoken amount phrase into amount_text.
Known customers: {top_50_customer_names_and_aliases}
```

Add 8–12 few-shot examples covering Hinglish, Hindi in Devanagari, Marathi, STT typos ("sau bis" means 120), and queries.

## Safety net

The LLM's amount is **only a suggestion**. `rules.py` independently parses `amount_text` and the transcript using `numbers_hi.py`. If the two disagree, the amount is null or the confidence is under 0.75, set `needs_confirmation=true` and read the amount back explicitly. Every money entry is confirmed anyway.

## Interface

`class IntentParser(Protocol): async def parse(transcript, ctx) -> ParsedIntent`. Implement `EvonParser`, `RulesParser`, and a `HybridParser` (Evon, then validation, then rules as fallback and cross-check). Tests use `FakeEvon` with canned JSON.

## In the interview

Explain why Evon plus rules beats either one alone: the LLM covers the variety of natural speech, while deterministic code guarantees money correctness.
