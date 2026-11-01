import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";

import { BottomNav } from "@/components/bottom-nav";
import { EntryList } from "@/components/entry-list";
import { getJson, type CustomerDetail } from "@/lib/api";
import { cn } from "@/lib/utils";

export const dynamic = "force-dynamic";

export default async function CustomerPage({ params }: { params: { id: string } }) {
  if (!/^\d+$/.test(params.id)) notFound();
  const c = await getJson<CustomerDetail>(`/customers/${params.id}`);
  if (!c) notFound();
  const owes = c.balance_paise > 0;

  return (
    <>
      <main className="mx-auto flex min-h-dvh max-w-md flex-col gap-5 px-4 pb-28 pt-6">
        <Link href="/customers" className="flex h-12 w-fit items-center gap-2 text-base font-semibold text-muted-foreground">
          <ArrowLeft className="h-5 w-5" aria-hidden /> Khate
        </Link>
        <header>
          <h1 className="text-3xl font-bold">{c.display_name}</h1>
          {c.aliases.length > 0 && <p className="text-muted-foreground">{c.aliases.join(", ")}</p>}
        </header>
        <section aria-label="Baaki" className={cn("rounded-2xl p-5", owes ? "bg-red-50" : "bg-green-50")}>
          <p className="text-base text-muted-foreground">{owes ? "Baaki hai" : c.balance_paise < 0 ? "Advance jama" : "Hisaab barabar"}</p>
          <p className={cn("text-4xl font-bold tabular-nums", owes ? "text-red-700" : "text-green-700")}>
            {c.balance_display.replace("-", "")}
          </p>
        </section>
        <section aria-labelledby="history" className="flex flex-col gap-3">
          <h2 id="history" className="text-lg font-bold">Hisaab</h2>
          <EntryList entries={c.entries} showCustomer={false} />
        </section>
      </main>
      <BottomNav active="customers" />
    </>
  );
}
