// Browser -> same-origin /api (Next rewrite -> FastAPI). Never surfaces raw errors.

import type { Turn } from "./voice-machine";

export class VoiceApiError extends Error {
  constructor(
    message: string,
    readonly offline = false,
  ) {
    super(message);
  }
}

async function parse(res: Response): Promise<Turn> {
  const body: unknown = await res.json().catch(() => null);
  if (res.ok && body && typeof body === "object" && "event_id" in body) return body as Turn;
  const msg =
    (body as { error?: { message?: string } } | null)?.error?.message ??
    "Kuch gadbad ho gayi. Dobara boliye.";
  throw new VoiceApiError(msg);
}

async function send(url: string, init: RequestInit): Promise<Turn> {
  if (typeof navigator !== "undefined" && !navigator.onLine) {
    throw new VoiceApiError("Internet nahi hai. Thodi der baad boliye.", true);
  }
  try {
    return await parse(await fetch(url, { ...init, signal: AbortSignal.timeout(20000) }));
  } catch (e) {
    if (e instanceof VoiceApiError) throw e;
    throw new VoiceApiError("Server se baat nahi ho payi. Dobara boliye.", true);
  }
}

export function audioForm(blob: Blob): FormData {
  const ext = blob.type.includes("mp4") ? "m4a" : blob.type.includes("ogg") ? "ogg" : "webm";
  const form = new FormData();
  form.append("audio", blob, `recording.${ext}`);
  return form;
}

export function postTurn(blob: Blob, idempotencyKey: string): Promise<Turn> {
  return send("/api/voice/turn", {
    method: "POST",
    body: audioForm(blob),
    headers: { "Idempotency-Key": idempotencyKey },
  });
}

export function postConfirmAudio(eventId: number, blob: Blob): Promise<Turn> {
  return send(`/api/voice/${eventId}/confirm`, { method: "POST", body: audioForm(blob) });
}

export function postConfirm(
  eventId: number,
  body: { accept?: boolean; customer_id?: number; amount_paise?: number },
): Promise<Turn> {
  return send(`/api/voice/${eventId}/confirm`, {
    method: "POST",
    body: JSON.stringify(body),
    headers: { "Content-Type": "application/json" },
  });
}
