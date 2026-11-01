"use client";

// The hero: one real exchange from the app. Shivani's two lines are the actual Timbre clips the
// app spoke during the first live test (no new credits); the shopkeeper's first line is what
// Prisma transcribed. Before "Suniye" is pressed the whole exchange is shown, so it reads
// without JavaScript or sound.

import { Check, Pause, Play } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { cn } from "@/components/cn";

type Step = { who: "you" | "khata"; text: string; audio?: string; ms?: number };

export const STEPS: Step[] = [
  { who: "you", text: "शर्मा जी ने 120 उधार लिए", ms: 1500 },
  { who: "khata", text: "Kaun se Sharma ji: Ramesh ya Suresh?", audio: "/audio/kaun-se-sharma.mp3" },
  { who: "you", text: "Ramesh", ms: 900 },
  { who: "khata", text: "Ramesh Sharma, ek sau bees rupaye udhaar. Sahi hai?", audio: "/audio/sahi-hai.mp3" },
  { who: "you", text: "Haan", ms: 800 },
];

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

export function VoiceDemo() {
  const [shown, setShown] = useState(STEPS.length);
  const [written, setWritten] = useState(true);
  const [speaking, setSpeaking] = useState<number | null>(null);
  const [playing, setPlaying] = useState(false);
  const run = useRef(0);
  const audio = useRef<HTMLAudioElement | null>(null);

  const stop = useCallback(() => {
    run.current += 1;
    audio.current?.pause();
    setPlaying(false);
    setSpeaking(null);
    setShown(STEPS.length);
    setWritten(true);
  }, []);

  useEffect(() => () => { run.current += 1; audio.current?.pause(); }, []);

  const play = useCallback(async () => {
    const id = ++run.current;
    setPlaying(true);
    setShown(0);
    setWritten(false);
    await sleep(300);
    for (let i = 0; i < STEPS.length; i++) {
      if (run.current !== id) return;
      const step = STEPS[i];
      setShown(i + 1);
      if (step.audio) {
        setSpeaking(i);
        await new Promise<void>((resolve) => {
          const a = new Audio(step.audio);
          audio.current = a;
          const done = () => resolve();
          a.onended = done;
          a.onerror = done;
          a.play().catch(() => setTimeout(done, 2500));
          setTimeout(done, 8000); // never hang on a stuck clip
        });
        setSpeaking(null);
        await sleep(350);
      } else {
        await sleep(step.ms ?? 900);
      }
    }
    if (run.current !== id) return;
    setWritten(true);
    setPlaying(false);
  }, []);

  return (
    <figure className="relative w-full max-w-[26rem] rounded-[1.75rem] bg-paper p-4 text-ink shadow-[0_30px_60px_-30px_rgba(0,0,0,0.55)] sm:p-5">
      <div className="flex items-center justify-between gap-3 px-1 pb-3">
        <span className="text-base font-semibold text-ink-soft">Ramesh Kirana Store</span>
        <button
          type="button"
          onClick={() => (playing ? stop() : void play())}
          className="flex h-12 items-center gap-2 rounded-full bg-marigold pl-3 pr-5 text-lg font-bold text-ink shadow-[0_3px_0_hsl(var(--marigold-deep))] active:translate-y-[3px] active:shadow-none"
        >
          {playing ? <Pause className="h-5 w-5" aria-hidden /> : <Play className="h-5 w-5 fill-current" aria-hidden />}
          {playing ? "Rokiye" : "Suniye"}
        </button>
      </div>

      <ol aria-label="Ek asli baat-cheet" className="flex min-h-[19rem] flex-col justify-end gap-2.5">
        {STEPS.slice(0, shown).map((s, i) => (
          <li
            key={i}
            className={cn(
              "max-w-[85%] animate-rise-in px-4 py-2.5 text-lg leading-snug",
              s.who === "you"
                ? "self-end rounded-[1.25rem] rounded-br-md bg-ink/[0.07] text-ink"
                : "flex items-start gap-2.5 rounded-[1.25rem] rounded-bl-md bg-white font-semibold shadow-[0_0_0_1px_hsl(var(--rule))]",
            )}
          >
            {s.who === "khata" && (
              <span aria-hidden className="mt-1.5 flex h-4 w-5 shrink-0 items-center gap-[3px]">
                {[0, 1, 2, 3].map((b) => (
                  <span
                    key={b}
                    className={cn("h-4 w-[3px] rounded-full bg-marigold-deep", speaking === i ? "animate-speak-bar" : "scale-y-50 opacity-60")}
                    style={{ animationDelay: `${b * 0.12}s` }}
                  />
                ))}
              </span>
            )}
            <span lang={s.who === "you" && /[ऀ-ॿ]/.test(s.text) ? "hi" : undefined}>
              {s.who === "you" ? `“${s.text}”` : s.text}
            </span>
          </li>
        ))}
      </ol>

      <div aria-live="polite" className="mt-4 min-h-[4.75rem]">
        {written && (
          <div className="ledger-margin flex animate-ink-in items-stretch overflow-hidden rounded-2xl bg-white shadow-[0_0_0_1px_hsl(var(--rule))] [--col:7rem]">
            <div className="min-w-0 flex-1 py-3 pl-4 pr-3">
              <p className="flex items-center gap-1.5 text-base font-semibold text-jama">
                <Check className="h-4 w-4" strokeWidth={3} aria-hidden /> Khate mein likh diya
              </p>
              <p className="truncate text-lg font-semibold leading-tight">Ramesh Sharma, udhaar</p>
            </div>
            <span className="num w-condensed flex w-[7rem] shrink-0 items-center justify-end pr-4 text-[1.75rem] font-bold text-udhaar">
              ₹120
            </span>
          </div>
        )}
      </div>
      <figcaption className="mt-3 px-1 text-sm text-ink-soft">
        App ki asli awaaz. Pehla vaakya dukaandaar ka hai, jaisa app ne suna.
      </figcaption>
    </figure>
  );
}
