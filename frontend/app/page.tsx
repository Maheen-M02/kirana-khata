import { AppHeader } from "@/components/app-header";
import { BottomNav } from "@/components/bottom-nav";
import { EntryList } from "@/components/entry-list";
import { VoiceConsole } from "@/components/voice-console";
import { getHealth, getJson, type Entry, type Sales } from "@/lib/api";
import { formatInr } from "@/lib/voice-machine";

export const dynamic = "force-dynamic";

export default async function Home() {
  const [health, me, sales, entries] = await Promise.all([
    getHealth(),
    getJson<{ name: string }>("/auth/me"),
    getJson<Sales>("/reports/today"),
    getJson<Entry[]>("/ledger/entries?day=today&limit=20"),
  ]);

  return (
    <>
      <main className="mx-auto flex min-h-dvh max-w-md flex-col px-4 pb-32 pt-5">
        <AppHeader shopName={me?.name} offline={health.status === "offline"} />

        <div className="mt-4 flex flex-col">
          <VoiceConsole />
        </div>

        <section aria-labelledby="today" className="mt-10 flex flex-col gap-4">
          <div className="flex items-end justify-between gap-4 px-1">
            <h2 id="today" className="text-2xl font-bold">Aaj ka khata</h2>
            {sales && <p className="text-base text-ink-soft">{sales.entries} entry</p>}
          </div>
          {sales && (
            <dl className="grid grid-cols-2 gap-3">
              <div className="rounded-[1.25rem] bg-ink px-5 py-4 text-white">
                <dt className="text-base text-white/75">Bikri</dt>
                <dd className="num w-condensed text-[2.25rem] font-bold leading-none">{sales.total_display}</dd>
              </div>
              <div className="rounded-[1.25rem] bg-jama-wash px-5 py-4">
                <dt className="text-base text-jama">Jama aaya</dt>
                <dd className="num w-condensed text-[2.25rem] font-bold leading-none text-jama">
                  {formatInr(sales.payments_paise)}
                </dd>
              </div>
            </dl>
          )}
          <EntryList entries={entries ?? []} />
        </section>
      </main>
      <BottomNav active="home" />
    </>
  );
}
