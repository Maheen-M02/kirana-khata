"use client";

// The one big mic button + the confirm card. Hold to talk, release to send.
// Everything a shopkeeper sees is driven by the pure reducer in lib/voice-machine.ts.

import { Check, Loader2, Mic, MicOff, Volume2, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useReducer, useRef, useState } from "react";

import { cn } from "@/lib/utils";
import { postConfirm, postConfirmAudio, postTurn, VoiceApiError } from "@/lib/voice-api";
import {
  COPY,
  initialState,
  isOpen,
  nextTarget,
  reducer,
  rupeesToPaise,
  type Turn,
} from "@/lib/voice-machine";

const MIN_MS = 400;
const MAX_MS = 25_000;

function pickMime(): string | undefined {
  if (typeof MediaRecorder === "undefined") return undefined;
  return ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"].find((m) =>
    MediaRecorder.isTypeSupported(m),
  );
}

export function VoiceConsole() {
  const [state, dispatch] = useReducer(reducer, initialState);
  const [amount, setAmount] = useState("");
  const router = useRouter();
  const recorder = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);
  const startedAt = useRef(0);
  const maxTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const audio = useRef<HTMLAudioElement | null>(null);
  const stateRef = useRef(state);
  stateRef.current = state;

  // Refresh server-rendered ledger views after every committed entry.
  useEffect(() => {
    if (state.committed > 0) router.refresh();
  }, [state.committed, router]);

  const handleTurn = useCallback((turn: Turn) => {
    dispatch({ type: "RESPONSE", turn });
    setAmount("");
    if (turn.confirm_audio_url) {
      audio.current?.pause();
      const a = new Audio(turn.confirm_audio_url);
      audio.current = a;
      a.onended = () => dispatch({ type: "AUDIO_ENDED" });
      a.onerror = () => dispatch({ type: "AUDIO_ENDED" });
      a.play().catch(() => dispatch({ type: "AUDIO_ENDED" }));
    }
  }, []);

  const fail = useCallback((e: unknown) => {
    if (e instanceof VoiceApiError && e.offline) dispatch({ type: "OFFLINE" });
    else dispatch({ type: "FAILED", message: e instanceof Error ? e.message : COPY.failed });
  }, []);

  const send = useCallback(
    async (blob: Blob) => {
      const target = nextTarget(stateRef.current);
      try {
        const turn =
          target.kind === "confirm"
            ? await postConfirmAudio(target.eventId, blob)
            : await postTurn(blob, crypto.randomUUID());
        handleTurn(turn);
      } catch (e) {
        fail(e);
      }
    },
    [fail, handleTurn],
  );

  const stop = useCallback(() => {
    if (maxTimer.current) clearTimeout(maxTimer.current);
    const rec = recorder.current;
    if (!rec || rec.state === "inactive") return;
    rec.stop();
  }, []);

  const start = useCallback(async () => {
    if (stateRef.current.phase === "thinking" || recorder.current?.state === "recording") return;
    audio.current?.pause(); // barge-in: talking stops Timbre
    dispatch({ type: "PRESS" });
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
    } catch {
      dispatch({ type: "PERMISSION_DENIED" });
      return;
    }
    const mimeType = pickMime();
    const rec = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
    chunks.current = [];
    rec.ondataavailable = (e) => e.data.size && chunks.current.push(e.data);
    rec.onstop = () => {
      stream.getTracks().forEach((t) => t.stop()); // mic light off between turns
      const held = Date.now() - startedAt.current;
      if (held < MIN_MS) {
        dispatch({ type: "TOO_SHORT" });
        return;
      }
      dispatch({ type: "RELEASE" });
      void send(new Blob(chunks.current, { type: rec.mimeType || "audio/webm" }));
    };
    recorder.current = rec;
    startedAt.current = Date.now();
    rec.start();
    dispatch({ type: "PERMISSION_OK" });
    maxTimer.current = setTimeout(stop, MAX_MS);
  }, [send, stop]);

  const tap = useCallback(
    async (body: { accept?: boolean; customer_id?: number; amount_paise?: number }) => {
      const t = stateRef.current.turn;
      if (!t) return;
      dispatch({ type: "TAP" });
      try {
        handleTurn(await postConfirm(t.event_id, body));
      } catch (e) {
        fail(e);
      }
    },
    [fail, handleTurn],
  );

  const { phase, turn, message } = state;
  const listening = phase === "listening";
  const busy = phase === "thinking";
  const paise = rupeesToPaise(amount);

  return (
    <section aria-label="Bolkar entry" className="flex w-full flex-col items-center gap-5">
      <p
        role="status"
        aria-live="polite"
        className={cn(
          "min-h-[4.5rem] w-full rounded-2xl px-4 py-3 text-center text-xl font-semibold leading-snug",
          phase === "blocked" ? "bg-destructive/10 text-destructive" : "bg-muted",
        )}
      >
        {phase === "speaking" && <Volume2 className="mr-2 inline h-5 w-5" aria-hidden />}
        {message}
      </p>

      {turn?.transcript && isOpen(turn) && (
        <p className="w-full text-center text-sm text-muted-foreground">Aapne kaha: “{turn.transcript}”</p>
      )}

      {isOpen(turn) && !busy && (turn!.stage === "confirm" || turn!.stage === "confirm_large") && (
        <div className="grid w-full grid-cols-2 gap-3">
          <button type="button" onClick={() => tap({ accept: false })}
            className="flex h-16 items-center justify-center gap-2 rounded-2xl border-2 border-destructive text-xl font-bold text-destructive">
            <X className="h-7 w-7" aria-hidden /> Nahi
          </button>
          <button type="button" onClick={() => tap({ accept: true })}
            className="flex h-16 items-center justify-center gap-2 rounded-2xl bg-green-700 text-xl font-bold text-white">
            <Check className="h-7 w-7" aria-hidden /> Haan
          </button>
        </div>
      )}

      {isOpen(turn) && !busy && turn!.stage === "disambiguate" && (
        <div className="flex w-full flex-col gap-2">
          {turn!.options.map((o) => (
            <button key={o.customer_id} type="button" onClick={() => tap({ customer_id: o.customer_id })}
              className="h-14 rounded-2xl border-2 border-primary text-lg font-semibold">
              {o.name}
            </button>
          ))}
          <button type="button" onClick={() => tap({ accept: false })}
            className="h-12 rounded-2xl text-base text-muted-foreground underline">
            Koi nahi, cancel
          </button>
        </div>
      )}

      {isOpen(turn) && !busy && turn!.stage === "amount" && (
        <form className="flex w-full gap-2" onSubmit={(e) => { e.preventDefault(); if (paise) void tap({ amount_paise: paise }); }}>
          <label htmlFor="amount" className="sr-only">Rakam (rupaye)</label>
          <input id="amount" inputMode="decimal" autoComplete="off" placeholder="₹ rakam"
            value={amount} onChange={(e) => setAmount(e.target.value)}
            className="h-14 min-w-0 flex-1 rounded-2xl border-2 px-4 text-xl" />
          <button type="submit" disabled={!paise}
            className="h-14 rounded-2xl bg-primary px-5 text-lg font-bold text-primary-foreground disabled:opacity-40">
            Theek
          </button>
        </form>
      )}

      <button
        type="button"
        aria-label={listening ? "Bol rahe hain — chhodne par bhejenge" : "Dabaye rakhiye aur boliye"}
        aria-pressed={listening}
        disabled={busy || phase === "blocked"}
        onPointerDown={(e) => { e.currentTarget.setPointerCapture?.(e.pointerId); void start(); }}
        onPointerUp={stop}
        onPointerCancel={stop}
        onKeyDown={(e) => { if ((e.key === " " || e.key === "Enter") && !e.repeat) { e.preventDefault(); void start(); } }}
        onKeyUp={(e) => { if (e.key === " " || e.key === "Enter") { e.preventDefault(); stop(); } }}
        onContextMenu={(e) => e.preventDefault()}
        className={cn(
          "relative flex h-44 w-44 touch-none select-none items-center justify-center rounded-full shadow-xl transition-transform",
          listening ? "scale-110 bg-red-600 text-white" : "bg-primary text-primary-foreground",
          (busy || phase === "blocked") && "opacity-60",
        )}
      >
        {listening && <span className="absolute inset-0 animate-ping rounded-full bg-red-500/40" aria-hidden />}
        {busy ? <Loader2 className="h-16 w-16 animate-spin" aria-hidden />
          : phase === "blocked" ? <MicOff className="h-16 w-16" aria-hidden />
          : <Mic className="h-16 w-16" aria-hidden />}
      </button>
      <p className="text-center text-sm text-muted-foreground">
        {isOpen(turn) ? "Jawab bolne ke liye bhi mic dabaiye" : "Jaise: “Sharma ji ne ek sau bees udhaar”"}
      </p>
    </section>
  );
}
