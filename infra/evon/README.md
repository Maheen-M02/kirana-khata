# Hosting Gnani Evon

Evon has no public hosted API, so we serve it ourselves behind an OpenAI-compatible `/v1/chat/completions`. The backend only needs `EVON_BASE_URL`, `EVON_MODEL=evon` and `EVON_API_KEY`, and it switches with `NLU_MODE`:

| `NLU_MODE` | Behaviour |
|---|---|
| `rules` (current default) | Deterministic parser only. No GPU needed; this is the demo fallback. |
| `hybrid` (target) | Evon for intent and wording; the rules parser re-checks every amount (see `docs/NLU.md`). |
| `evon` | Evon only. Used for evaluation, never for money in production. |

## Option 1 (recommended): Modal + vLLM on one H100

The script is [`modal_vllm.py`](modal_vllm.py). It's prepared but not deployed, because it costs GPU time.

```bash
pip install modal && modal setup
modal secret create evon-api-key EVON_API_KEY=$(python -c "import secrets;print(secrets.token_urlsafe(32))")
modal deploy infra/evon/modal_vllm.py
curl -H "Authorization: Bearer $EVON_API_KEY" https://<you>--kirana-evon-serve.modal.run/v1/models   # warm-up
```

Then set `EVON_BASE_URL=https://<you>--kirana-evon-serve.modal.run/v1` and `NLU_MODE=hybrid`, and run `make test-live` to score the golden set on real Evon.

- **Cold start:** downloading the model and loading vLLM takes minutes on the first boot, then gets faster with the cached volumes. It scales to zero after 15 idle minutes. **Warm it up before filming.**
- **Flags** are taken from the HF model card (2026-11-01): `--trust-remote-code --enable-auto-tool-choice --tool-call-parser qwen3_coder --reasoning-parser nano_v3`, vLLM ≥ 0.12.
- **Thinking off:** set per request (`chat_template_kwargs.enable_thinking=false`). The card recommends temperature 0.6 for chat; we use 0.2 for near-deterministic extraction.

## Option 2: RunPod / any GPU VM

```bash
pip install -U "vllm>=0.12.0"
vllm serve gnani/gnani-evon-v3.3-30B-A3B --served-model-name evon --max-model-len 16384 \
  --trust-remote-code --enable-auto-tool-choice --tool-call-parser qwen3_coder \
  --reasoning-parser nano_v3 --api-key "$EVON_API_KEY" --port 8080
```

## Option 3: local GGUF

The architecture is `nemotron_h` (a Mamba2-Transformer hybrid MoE). Check that your llama.cpp or Ollama build supports it before relying on this option. The model card only links to a "Browse Quantizations" page.

## SGLang (from the model card)

```bash
python -m sglang.launch_server --model-path gnani/gnani-evon-v3.3 --served-model-name evon \
  --dtype bfloat16 --context-length 16384 --mem-fraction-static 0.90 --moe-runner-backend triton \
  --host 0.0.0.0 --port 30000
```

Note that the card uses both `gnani/gnani-evon-v3.3` and `gnani/gnani-evon-v3.3-30B-A3B` as repo IDs. If one 404s, use the other (`EVON_HF_MODEL` in the Modal script).
