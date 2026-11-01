"use client";

import { Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";

import { cn } from "@/lib/utils";

/** Keep the last 10 digits, so "+91 98765-43210" and "098765 43210" both work. */
export function phoneDigits(input: string): string {
  const d = input.replace(/\D/g, "");
  return d.length > 10 ? d.slice(-10) : d;
}

function formatPhone(d: string): string {
  return d.length > 5 ? `${d.slice(0, 5)} ${d.slice(5)}` : d;
}

export function LoginForm() {
  const router = useRouter();
  const [phone, setPhone] = useState("");
  const [pin, setPin] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [pinFocus, setPinFocus] = useState(false);
  const pinRef = useRef<HTMLInputElement>(null);
  const ready = phone.length === 10 && pin.length === 4;

  async function login(p: string, code: string) {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone: p, pin: code }),
      });
      if (res.ok) {
        router.replace("/");
        router.refresh();
        return;
      }
      const body = (await res.json().catch(() => null)) as { error?: { message?: string } } | null;
      setError(body?.error?.message ?? "Phone ya PIN galat hai.");
    } catch {
      setError("Server se baat nahi ho payi. Dobara koshish kijiye.");
    }
    setBusy(false);
    setPin("");
    pinRef.current?.focus();
  }

  function onPin(value: string) {
    const next = value.replace(/\D/g, "").slice(0, 4);
    setPin(next);
    if (next.length === 4 && phone.length === 10 && !busy) void login(phone, next);
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (ready && !busy) void login(phone, pin);
      }}
      className="mt-7 flex flex-col gap-6"
      noValidate
    >
      <div className="flex flex-col gap-2">
        <label htmlFor="phone" className="text-lg font-semibold">Mobile number</label>
        <div className="flex h-16 items-center rounded-2xl border-2 border-input bg-white px-4 focus-within:border-ink">
          <span className="num pr-3 text-xl font-semibold text-ink-soft" aria-hidden>+91</span>
          <span className="mr-3 h-7 w-px bg-rule" aria-hidden />
          <input
            id="phone"
            className="num h-full min-w-0 flex-1 bg-transparent text-2xl font-semibold tracking-wide outline-none placeholder:text-ink-soft/40"
            type="tel"
            inputMode="numeric"
            autoComplete="tel-national"
            required
            value={formatPhone(phone)}
            onChange={(e) => {
              const d = phoneDigits(e.target.value);
              setPhone(d);
              if (d.length === 10 && phone.length < 10) pinRef.current?.focus();
            }}
            placeholder="98765 43210"
          />
        </div>
      </div>

      <div className="flex flex-col gap-2">
        <label htmlFor="pin" className="text-lg font-semibold">4 ank ka PIN</label>
        <div className="relative">
          <div className="grid grid-cols-4 gap-3" aria-hidden>
            {[0, 1, 2, 3].map((i) => (
              <span
                key={i}
                className={cn(
                  "flex h-16 items-center justify-center rounded-2xl border-2 bg-white transition-colors",
                  i < pin.length ? "border-ink" : "border-input",
                  pinFocus && i === Math.min(pin.length, 3) && "border-ink ring-4 ring-marigold/40",
                )}
              >
                {i < pin.length && <span className="h-3.5 w-3.5 rounded-full bg-ink" />}
              </span>
            ))}
          </div>
          {/* One real input over the boxes: keeps paste, autofill and screen readers simple. */}
          <input
            id="pin"
            ref={pinRef}
            type="password"
            inputMode="numeric"
            autoComplete="current-password"
            pattern="\d{4}"
            maxLength={4}
            required
            value={pin}
            onChange={(e) => onPin(e.target.value)}
            onFocus={() => setPinFocus(true)}
            onBlur={() => setPinFocus(false)}
            className="absolute inset-0 h-full w-full bg-transparent text-transparent caret-transparent outline-none focus-visible:outline-none"
          />
        </div>
      </div>

      {error && (
        <p role="alert" className="rounded-2xl bg-udhaar-wash px-4 py-3 text-lg font-semibold text-udhaar">
          {error}
        </p>
      )}

      <button
        type="submit"
        disabled={busy || !ready}
        className="flex h-16 items-center justify-center gap-3 rounded-2xl bg-marigold text-xl font-bold text-ink shadow-[0_2px_0_hsl(var(--marigold-deep))] transition active:translate-y-[2px] active:shadow-none disabled:bg-muted disabled:text-ink-soft disabled:shadow-none"
      >
        {busy && <Loader2 className="h-6 w-6 animate-spin" aria-hidden />}
        {busy ? "Khol rahe hain…" : "Andar aaiye"}
      </button>
    </form>
  );
}
