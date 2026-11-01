import { ArrowLeft, Mic } from "lucide-react";
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
  const advance = c.balance_paise < 0;
  const status = owes ? "Baaki hai" : advance ? "Advance jama hai" : "Hisaab barabar";

  return (
    <>
      <main className="mx-auto flex min-h-dvh max-w-md flex-col px-4 pb-32 pt-3">
        <Link href="/customers" className="-ml-1 flex h-12 w-fit items-center gap-2 px-1 text-lg font-semibold text-ink-soft">
          <ArrowLeft className="h-5 w-5" aria-hidden /> Khate
        </Link>

        <header className="mt-2 px-1">
          <h1 className="w-wide text-[2.25rem] font-bold leading-[1.05] tracking-tight">{c.display_name}</h1>
          {c.aliases.length > 0 && (
            <p className="mt-1 text-lg text-ink-soft">Bulate hain: {c.aliases.join(", ")}</p>
          )}
        </header>

        <section
          aria-label={status}
          className={cn(
            "mt-5 rounded-[1.5rem] px-6 py-5",
            owes ? "bg-udhaar-wash" : advance ? "bg-jama-wash" : "bg-white shadow-[0_0_0_1px_hsl(var(--rule))]",
          )}
        >
          <p className={cn("text-lg font-semibold", owes ? "text-udhaar" : advance ? "text-jama" : "text-ink-soft")}>
            {status}
          </p>
          <p
            className={cn(
              "num w-condensed mt-1 text-[3.5rem] font-bold leading-none",
              owes ? "text-udhaar" : advance ? "text-jama" : "text-ink",
            )}
          >
            {c.balance_display.replace("-", "")}
          </p>
        </section>

        <Link
          href="/"
          className="mt-3 flex items-center gap-3 rounded-[1.25rem] bg-marigold-wash px-5 py-3.5 text-lg leading-snug"
        >
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-marigold text-ink">
            <Mic className="h-5 w-5" strokeWidth={2.5} aria-hidden />
          </span>
          <span>
            Paise mile? Boliye: <span className="font-semibold">“{c.display_name} ne sau rupaye jama kiye”</span>
          </span>
        </Link>

        <section aria-labelledby="history" className="mt-8 flex flex-col gap-4">
          <h2 id="history" className="px-1 text-2xl font-bold">Hisaab</h2>
          <EntryList entries={c.entries} showCustomer={false} withDate empty="Is khate mein abhi koi entry nahi." />
        </section>
      </main>
      <BottomNav active="customers" />
    </>
  );
}
