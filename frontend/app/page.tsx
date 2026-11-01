import { BottomNav } from "@/components/bottom-nav";
import { EntryList } from "@/components/entry-list";
import { VoiceConsole } from "@/components/voice-console";
import { getHealth, getJson, type Entry, type Sales } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function Home() {
  const [health, sales, entries] = await Promise.all([
    getHealth(),
    getJson<Sales>("/reports/today"),
    getJson<Entry[]>("/ledger/entries?day=today&limit=20"),
  ]);

  return (
    <>
      <main className="mx-auto flex min-h-dvh max-w-md flex-col gap-6 px-4 pb-28 pt-6">
        <header className="flex items-center justify-between">
          <h1 className="text-2xl font-bold tracking-tight">Kirana Khata</h1>
          {health.status === "offline" && (
            <span role="alert" className="rounded-full bg-destructive px-3 py-1 text-sm font-semibold text-destructive-foreground">
              Server band hai
            </span>
          )}
        </header>

        <VoiceConsole />

        <section aria-labelledby="today" className="flex flex-col gap-3">
          <div className="flex items-baseline justify-between">
            <h2 id="today" className="text-lg font-bold">Aaj</h2>
            {sales && (
              <p className="text-base">
                Bikri <span className="font-bold tabular-nums">{sales.total_display}</span>
                <span className="text-muted-foreground"> · {sales.entries} entry</span>
              </p>
            )}
          </div>
          <EntryList entries={entries ?? []} />
        </section>
      </main>
      <BottomNav active="home" />
    </>
  );
}
