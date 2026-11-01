import { ChevronRight } from "lucide-react";
import Link from "next/link";

import { BottomNav } from "@/components/bottom-nav";
import { getJson, type Customer } from "@/lib/api";
import { cn } from "@/lib/utils";
import { formatInr } from "@/lib/voice-machine";

export const dynamic = "force-dynamic";
export const metadata = { title: "Khate · Kirana Khata" };

export default async function CustomersPage() {
  const customers = (await getJson<Customer[]>("/customers")) ?? [];
  const owing = [...customers].sort((a, b) => b.balance_paise - a.balance_paise);
  const total = customers.reduce((s, c) => s + Math.max(c.balance_paise, 0), 0);

  return (
    <>
      <main className="mx-auto flex min-h-dvh max-w-md flex-col gap-4 px-4 pb-28 pt-6">
        <h1 className="text-2xl font-bold">Khate</h1>
        <p className="text-base text-muted-foreground">
          {customers.length} customer · kul baaki{" "}
          <span className="font-bold text-foreground tabular-nums">{formatInr(total)}</span>
        </p>
        {owing.length === 0 ? (
          <p className="py-10 text-center text-muted-foreground">
            Abhi koi customer nahi. Mic dabaake pehli entry boliye.
          </p>
        ) : (
          <ul className="divide-y rounded-2xl border">
            {owing.map((c) => (
              <li key={c.id}>
                <Link href={`/customers/${c.id}`} className="flex min-h-16 items-center justify-between gap-3 px-4 py-3">
                  <span className="min-w-0">
                    <span className="block truncate text-lg font-semibold">{c.display_name}</span>
                    {c.aliases.length > 0 && (
                      <span className="block truncate text-sm text-muted-foreground">{c.aliases.join(", ")}</span>
                    )}
                  </span>
                  <span className="flex shrink-0 items-center gap-1">
                    <span className={cn("text-lg font-bold tabular-nums",
                      c.balance_paise > 0 ? "text-red-700" : c.balance_paise < 0 ? "text-green-700" : "text-muted-foreground")}>
                      {c.balance_display}
                    </span>
                    <ChevronRight className="h-5 w-5 text-muted-foreground" aria-hidden />
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </main>
      <BottomNav active="customers" />
    </>
  );
}
