"""Serve Gnani Evon on Modal with vLLM behind an OpenAI-compatible API.

Prepared, NOT deployed. Deploying spends GPU money; run only when the owner says so:

    pip install modal && modal setup
    modal secret create evon-api-key EVON_API_KEY=<long-random-string>
    modal deploy infra/evon/modal_vllm.py          # prints https://<you>--kirana-evon-serve.modal.run
    # .env: EVON_BASE_URL=https://<...>.modal.run/v1  EVON_API_KEY=<same>  NLU_MODE=hybrid

Flags come from the HF model card (checked 2026-11-01): vLLM >= 0.12, --trust-remote-code,
--tool-call-parser qwen3_coder, --reasoning-parser nano_v3. Thinking is turned off per request
(`chat_template_kwargs.enable_thinking=false`, see app/nlu/evon_client.py). Prompts are short,
so --max-model-len 16384 saves memory. Model: nemotron_h hybrid MoE, 30B total / ~3.5B active,
BF16 -> one 80 GB GPU (A100-80GB default; H100 is faster but burns credits ~1.6x). Scales to zero after 15 idle minutes: WARM IT UP
(`make evon-warm`) before filming. Check Modal's docs if a decorator name has changed.
"""

from __future__ import annotations

import os
import subprocess

import modal

MODEL = os.environ.get("EVON_HF_MODEL", "gnani/gnani-evon-v3.3-30B-A3B")
PORT = 8000

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("vllm>=0.12.0", "huggingface_hub[hf_transfer]")
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1"})
)
hf_cache = modal.Volume.from_name("evon-hf-cache", create_if_missing=True)
vllm_cache = modal.Volume.from_name("evon-vllm-cache", create_if_missing=True)

app = modal.App("kirana-evon")


@app.function(
    image=image,
    gpu="A100-80GB",  # $30/mo Modal Starter credits ~= 12 h here (H100 ~= 7.5 h)
    scaledown_window=15 * 60,
    timeout=60 * 60,
    volumes={"/root/.cache/huggingface": hf_cache, "/root/.cache/vllm": vllm_cache},
    secrets=[modal.Secret.from_name("evon-api-key")],
)
@modal.concurrent(max_inputs=16)
@modal.web_server(port=PORT, startup_timeout=20 * 60)
def serve() -> None:
    cmd = [
        "vllm", "serve", MODEL,
        "--served-model-name", "evon",
        "--host", "0.0.0.0", "--port", str(PORT),
        "--max-model-len", "16384",
        "--trust-remote-code",
        "--enable-auto-tool-choice", "--tool-call-parser", "qwen3_coder",
        "--reasoning-parser", "nano_v3",
        "--api-key", os.environ["EVON_API_KEY"],
    ]  # fmt: skip
    subprocess.Popen(cmd)  # noqa: S603
