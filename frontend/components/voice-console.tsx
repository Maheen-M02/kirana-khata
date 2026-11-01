"use client";

// The one big mic button + the confirm card. Hold to talk, release to send.
// Everything a shopkeeper sees is driven by the pure reducer in lib/voice-machine.ts.

import { Check, Mic, MicOff, X } from "lucide-react";
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
  const ringRef = useRef<HTMLSpanElement | null>(null);
  const meter = useRef<{ ctx: AudioContext; raf: number } | null>(null);

  // Live input level -> CSS var on the ring, so the shopkeeper can see the mic hears them.
  const startMeter = useCallback((stream: MediaStream) => {
    const Ctx = typeof window !== "undefined" ? window.AudioContext : undefined;
    if (!Ctx || !ringRef.current) return;
    try {
      const ctx = new Ctx();
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 512;
      ctx.createMediaStreamSource(stream).connect(analyser);
      const buf = new Uint8Array(analyser.fftSize);
      const tick = () => {
        analyser.getByteTimeDomainData(buf);
        let sum = 0;
        for (let i = 0; i < buf.length; i++) sum += (buf[i] - 128) ** 2;
        const level = Math.min(1, Math.sqrt(sum / buf.length) / 40);
        ringRef.current?.style.setProperty("--level", level.toFixed(3));
        meter.current = { ctx, raf: requestAnimationFrame(tick) };
      };
      tick();
    } catch {
      /* metering is decoration; recording works without it */
    }
  }, []);

  const stopMeter = useCallback(() => {
    if (!meter.current) return;
    cancelAnimationFrame(meter.current.raf);
    void meter.current.ctx.close().catch(() => undefined);
    meter.current = null;
    ringRef.current?.style.setProperty("--level", "0");
  }, []);

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
      stopMeter();
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
    startMeter(stream);
    dispatch({ type: "PERMISSION_OK" });
    maxTimer.current = setTimeout(stop, MAX_MS);
  }, [send, stop, startMeter, stopMeter]);

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
  const blocked = phase === "blocked";
  const open = isOpen(turn) && !busy;
  const paise = rupeesToPaise(amount);
  const askConfirm = open && (turn!.stage === "confirm" || turn!.stage === "confirm_large");

  return (
    <section aria-label="Bolkar entry" className="flex w-full flex-col items-center">
      {/* The conversation: what you said, and what the khata says back. */}
      <div className="flex min-h-[7rem] w-full flex-col justify-end gap-3">
        {turn?.transcript && isOpen(turn) && (
          <p className="max-w-[88%] self-end rounded-[1.25rem] rounded-br-md bg-ink/[0.06] px-4 py-2.5 text-lg leading-snug text-ink-soft">
            Aapne kaha: “{turn.transcript}”
          </p>
        )}
        <div
          className={cn(
            "flex w-full items-start gap-3 rounded-[1.25rem] px-5 py-4",
            !open && !blocked && "justify-center text-center",
            blocked
              ? "bg-udhaar-wash text-udhaar"
              : open
                ? "bg-white shadow-[0_0_0_1px_hsl(var(--rule))]"
                : "",
          )}
        >
          <StateGlyph phase={phase} />
          <p
            role="status"
            aria-live="polite"
            className={cn(
              "min-w-0 text-balance font-semibold leading-tight",
              open || blocked ? "flex-1" : "flex-initial",
              open || blocked ? "text-2xl" : "text-[1.7rem]",
            )}
          >
            {/* Keyed inner span re-animates each new line; the live region itself stays mounted. */}
            <span key={message} className="block animate-rise-in">{message}</span>
          </p>
        </div>
      </div>

      {askConfirm && (
        <div className="mt-4 grid w-full animate-rise-in grid-cols-[1fr_1.4fr] gap-3">
          <button
            type="button"
            onClick={() => tap({ accept: false })}
            className="flex h-16 items-center justify-center gap-2 rounded-2xl border-2 border-udhaar/40 bg-white text-xl font-bold text-udhaar active:bg-udhaar-wash"
          >
            <X className="h-7 w-7" aria-hidden /> Nahi
          </button>
          <button
            type="button"
            onClick={() => tap({ accept: true })}
            className="flex h-16 items-center justify-center gap-2 rounded-2xl bg-jama text-xl font-bold text-white shadow-[0_3px_0_hsl(162_72%_17%)] active:translate-y-[3px] active:shadow-none"
          >
            <Check className="h-7 w-7" strokeWidth={3} aria-hidden /> Haan
          </button>
        </div>
      )}

      {open && turn!.stage === "disambiguate" && (
        <div className="mt-4 flex w-full animate-rise-in flex-col gap-2.5">
          {turn!.options.map((o) => (
            <button
              key={o.customer_id}
              type="button"
              onClick={() => tap({ customer_id: o.customer_id })}
              className="flex h-16 items-center rounded-2xl border-2 border-ink/15 bg-white px-5 text-left text-xl font-semibold active:border-ink"
            >
              {o.name}
            </button>
          ))}
          <button
            type="button"
            onClick={() => tap({ accept: false })}
            className="h-12 rounded-2xl text-lg font-semibold text-ink-soft underline decoration-rule decoration-2 underline-offset-4"
          >
            Koi nahi, cancel
          </button>
        </div>
      )}

      {open && turn!.stage === "amount" && (
        <form
          className="mt-4 flex w-full animate-rise-in gap-2.5"
          onSubmit={(e) => {
            e.preventDefault();
            if (paise) void tap({ amount_paise: paise });
          }}
        >
          <label htmlFor="amount" className="sr-only">Rakam (rupaye)</label>
          <div className="flex h-16 min-w-0 flex-1 items-center rounded-2xl border-2 border-input bg-white px-4 focus-within:border-ink">
            <span className="pr-2 text-2xl font-semibold text-ink-soft" aria-hidden>₹</span>
            <input
              id="amount"
              inputMode="decimal"
              autoComplete="off"
              placeholder="rakam"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              className="num w-condensed h-full min-w-0 flex-1 bg-transparent text-3xl font-bold outline-none placeholder:text-xl placeholder:font-normal placeholder:text-ink-soft/50"
            />
          </div>
          <button
            type="submit"
            disabled={!paise}
            className="h-16 rounded-2xl bg-ink px-6 text-xl font-bold text-white disabled:bg-muted disabled:text-ink-soft"
          >
            Theek
          </button>
        </form>
      )}

      {/* The one big button. Marigold at rest, ink while it listens; the ring follows your voice. */}
      <div className="relative mt-7 flex h-56 w-56 items-center justify-center">
        <span
          ref={ringRef}
          aria-hidden
          style={{ "--level": 0 } as React.CSSProperties}
          className={cn(
            "pointer-events-none absolute inset-0 rounded-full bg-marigold/30 transition-[transform,opacity] duration-75",
            listening ? "opacity-100 [transform:scale(calc(0.8+var(--level)*0.4))]" : "scale-75 opacity-0",
          )}
        />
        <button
          type="button"
          aria-label={listening ? "Bol rahe hain, chhodne par bhejenge" : "Dabaye rakhiye aur boliye"}
          aria-pressed={listening}
          disabled={busy || blocked}
          onPointerDown={(e) => {
            e.currentTarget.setPointerCapture?.(e.pointerId);
            void start();
          }}
          onPointerUp={stop}
          onPointerCancel={stop}
          onKeyDown={(e) => {
            if ((e.key === " " || e.key === "Enter") && !e.repeat) {
              e.preventDefault();
              void start();
            }
          }}
          onKeyUp={(e) => {
            if (e.key === " " || e.key === "Enter") {
              e.preventDefault();
              stop();
            }
          }}
          onContextMenu={(e) => e.preventDefault()}
          className={cn(
            "relative flex h-44 w-44 touch-none select-none items-center justify-center rounded-full transition-[transform,background-color,box-shadow,color] duration-150",
            busy || blocked
              ? "bg-muted text-ink-soft"
              : listening
                ? "scale-95 bg-ink text-marigold shadow-[0_0_0_6px_hsl(var(--marigold))]"
                : "bg-marigold text-ink shadow-[0_6px_0_hsl(var(--marigold-deep)),0_22px_40px_-14px_hsl(var(--marigold-deep)/0.7)] active:translate-y-[4px] active:shadow-[0_2px_0_hsl(var(--marigold-deep))]",
          )}
        >
          {blocked ? (
            <MicOff className="h-16 w-16" aria-hidden />
          ) : (
            <Mic className="h-[4.5rem] w-[4.5rem]" strokeWidth={2.25} aria-hidden />
          )}
        </button>
      </div>

      <p className="mt-2 max-w-[30ch] text-balance text-center text-lg leading-snug text-ink-soft">
        {listening
          ? "Bolte rahiye. Chhodte hi bhej denge."
          : isOpen(turn)
            ? "Jawab bolne ke liye bhi mic dabaiye, ya upar tap kijiye."
            : "Jaise: “Sharma ji ne ek sau bees udhaar liya”"}
      </p>
    </section>
  );
}

/** Small live indicator beside the message: listening, thinking or speaking. */
function StateGlyph({ phase }: { phase: string }) {
  const box = "mt-1.5 flex h-6 w-7 shrink-0 items-center justify-center gap-[3px]";
  if (phase === "thinking") {
    return (
      <span className={box} aria-hidden>
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="h-2 w-2 animate-ink-dot rounded-full bg-ink"
            style={{ animationDelay: `${i * 0.15}s` }}
          />
        ))}
      </span>
    );
  }
  if (phase === "speaking" || phase === "listening") {
    return (
      <span className={box} aria-hidden>
        {[0, 1, 2, 3].map((i) => (
          <span
            key={i}
            className={cn(
              "h-6 w-1 origin-center animate-speak-bar rounded-full",
              phase === "listening" ? "bg-udhaar" : "bg-marigold-deep",
            )}
            style={{ animationDelay: `${i * 0.12}s` }}
          />
        ))}
      </span>
    );
  }
  return null;
}
