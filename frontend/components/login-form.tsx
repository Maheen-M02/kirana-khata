"use client";

import { Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

export function LoginForm() {
  const router = useRouter();
  const [phone, setPhone] = useState("");
  const [pin, setPin] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone, pin }),
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
    } finally {
      setBusy(false);
    }
  }

  const field = "h-14 w-full rounded-2xl border-2 px-4 text-xl";
  return (
    <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
      <label className="flex flex-col gap-2 text-lg font-semibold">
        Mobile number
        <input className={field} type="tel" inputMode="numeric" autoComplete="tel" required
          value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="98765 43210" />
      </label>
      <label className="flex flex-col gap-2 text-lg font-semibold">
        4 ank ka PIN
        <input className={`${field} tracking-[0.5em]`} type="password" inputMode="numeric"
          autoComplete="current-password" pattern="\d{4}" maxLength={4} required
          value={pin} onChange={(e) => setPin(e.target.value.replace(/\D/g, "").slice(0, 4))} />
      </label>
      {error && <p role="alert" className="rounded-xl bg-destructive/10 px-4 py-3 text-base font-semibold text-destructive">{error}</p>}
      <button type="submit" disabled={busy || pin.length !== 4 || phone.replace(/\D/g, "").length < 10}
        className="flex h-14 items-center justify-center gap-2 rounded-2xl bg-primary text-xl font-bold text-primary-foreground disabled:opacity-40">
        {busy && <Loader2 className="h-6 w-6 animate-spin" aria-hidden />} Andar aaiye
      </button>
    </form>
  );
}
