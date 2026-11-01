import { ChevronRight } from "lucide-react";
import Link from "next/link";

import { BottomNav } from "@/components/bottom-nav";
import { LogoutButton } from "@/components/logout-button";
import { getJson, type Customer } from "@/lib/api";
import { cn } from "@/lib/utils";
import { formatInr } from "@/lib/voice-machine";

export const dynamic = "force-dynamic";
export const metadata = { title: "Khate · Kirana Khata" };

export default async function CustomersPage() {
  const customers = (await getJson<Customer[]>("/customers")) ?? [];
  const owing = [...customers].sort((a, b) => b.balance_paise - a.balance_paise);
  const total = customers.reduce((s, c) => s + Math.max(c.balance_paise, 0), 0);
  const max = Math.max(1, ...customers.map((c) => c.balance_paise));
  const withDues = customers.filter((c) => c.balance_paise > 0).length;

  return (
    <>
      <main className="mx-auto flex min-h-dvh max-w-md flex-col px-4 pb-32 pt-5">
        <div className="flex items-center justify-between">
          <h1 className="w-wide text-3xl font-bold tracking-tight">Khate</h1>
          <LogoutButton />
        </div>

        <section aria-label="Kul baaki" className="mt-4 rounded-[1.5rem] bg-ink px-6 py-5 text-white">
          <p className="text-lg text-white/75">Kul baaki, sab customer milaake</p>
          <p className="num w-condensed mt-1 text-[3.25rem] font-bold leading-none">{formatInr(total)}</p>
          <p className="mt-3 text-base text-white/75">
            {withDues} logon se lena hai, kul {customers.length} khate
          </p>
        </section>

        {owing.length === 0 ? (
          <p className="mt-6 rounded-[1.25rem] border-2 border-dashed border-rule px-6 py-10 text-center text-lg text-ink-soft">
            Abhi koi khata nahi. Mic dabaake boliye, jaise “Sharma ji ne sau rupaye udhaar liye”.
          </p>
        ) : (
          <ul className="ledger-margin mt-6 overflow-hidden rounded-[1.25rem] bg-white shadow-[0_0_0_1px_hsl(var(--rule))]">
            {owing.map((c) => {
              const owes = c.balance_paise > 0;
              return (
                <li key={c.id} className="border-b border-rule last:border-b-0">
                  <Link href={`/customers/${c.id}`} className="flex min-h-[4.75rem] items-stretch active:bg-paper">
                    <span className="min-w-0 flex-1 py-3 pl-5 pr-3">
                      <span className="block truncate text-xl font-semibold leading-tight">{c.display_name}</span>
                      {c.aliases.length > 0 && (
                        <span className="mt-0.5 block truncate text-base text-ink-soft">{c.aliases.join(", ")}</span>
                      )}
                      {owes && (
                        <span aria-hidden className="mt-2 block h-1 rounded-full bg-udhaar-wash">
                          <span className="block h-full rounded-full bg-udhaar/70" style={{ width: `${Math.max(6, (c.balance_paise / max) * 100)}%` }} />
                        </span>
                      )}
                    </span>
                    <span className="flex w-[7.5rem] shrink-0 items-center justify-end gap-1 pr-3">
                      <span
                        className={cn(
                          "num w-condensed text-[1.6rem] font-bold",
                          owes ? "text-udhaar" : c.balance_paise < 0 ? "text-jama" : "text-ink-soft",
                        )}
                      >
                        {c.balance_display.replace("-", "")}
                      </span>
                      <ChevronRight className="h-5 w-5 shrink-0 text-ink-soft/60" aria-hidden />
                    </span>
                  </Link>
                </li>
              );
            })}
          </ul>
        )}
      </main>
      <BottomNav active="customers" />
    </>
  );
}
