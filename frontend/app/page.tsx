import { Mic } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { getHealth } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function Home() {
  const health = await getHealth();
  const online = health.status === "online";

  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col items-center justify-between px-4 py-8">
      <header className="flex w-full items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight">Kirana Khata</h1>
        <Badge variant={online ? "default" : "destructive"} aria-live="polite">
          {online ? "Server chalu hai" : "Server band hai"}
        </Badge>
      </header>

      <section className="flex flex-col items-center gap-6 text-center">
        <p className="text-lg text-muted-foreground">Bolo, aur hisaab likh jayega.</p>
        {/* Recorder arrives in Phase 5 — placeholder keeps the one-thumb layout honest. */}
        <button
          type="button"
          disabled
          aria-label="Bolne ke liye dabaye rakhiye (jaldi aa raha hai)"
          className="flex h-40 w-40 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg disabled:opacity-60"
        >
          <Mic className="h-16 w-16" aria-hidden />
        </button>
        <p className="text-sm text-muted-foreground">Dabaye rakhiye aur boliye — jaldi aa raha hai</p>
      </section>

      <footer className="text-xs text-muted-foreground">Built on Gnani AI · Prisma · Evon · Timbre</footer>
    </main>
  );
}
