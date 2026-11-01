import type { Entry } from "@/lib/api";
import { cn } from "@/lib/utils";

const LABEL: Record<Entry["type"], string> = {
  credit_sale: "Udhaar",
  payment_received: "Jama",
  cash_sale: "Nakad",
  adjustment: "Badlav",
};

const timeOnly = new Intl.DateTimeFormat("en-IN", {
  hour: "numeric",
  minute: "2-digit",
  timeZone: "Asia/Kolkata",
});
const dateTime = new Intl.DateTimeFormat("en-IN", {
  day: "numeric",
  month: "short",
  hour: "numeric",
  minute: "2-digit",
  timeZone: "Asia/Kolkata",
});

function tone(e: Entry, cancelled: boolean): string {
  if (e.is_reversal || cancelled) return "text-ink-soft";
  if (e.type === "credit_sale") return "text-udhaar";
  if (e.type === "payment_received") return "text-jama";
  return "text-ink";
}

/** A page of the khata: one ruled row per entry, amounts in the column right of the red margin. */
export function EntryList({
  entries,
  showCustomer = true,
  withDate = false,
  empty = "Abhi koi entry nahi. Mic dabaake pehli entry boliye.",
}: {
  entries: Entry[];
  showCustomer?: boolean;
  withDate?: boolean;
  empty?: string;
}) {
  if (entries.length === 0) {
    return (
      <p className="rounded-[1.25rem] border-2 border-dashed border-rule px-6 py-8 text-center text-lg text-ink-soft">
        {empty}
      </p>
    );
  }
  const fmt = withDate ? dateTime : timeOnly;
  return (
    <ul className="ledger-margin overflow-hidden rounded-[1.25rem] bg-white shadow-[0_0_0_1px_hsl(var(--rule))]">
      {entries.map((e) => {
        const cancelled = e.reversed_by !== null;
        const label = e.is_reversal ? "Cancel" : LABEL[e.type];
        const title = showCustomer
          ? e.customer_name ?? (e.type === "cash_sale" ? "Nakad bikri" : label)
          : label;
        const items = e.lines.map((l) => l.item_name).join(", ");
        return (
          <li key={e.id} className="flex min-h-[4.5rem] items-stretch border-b border-rule last:border-b-0">
            <div className={cn("min-w-0 flex-1 py-3 pl-5 pr-3", cancelled && "opacity-55")}>
              <p className={cn("truncate text-xl font-semibold leading-tight", cancelled && "line-through")}>
                {title}
              </p>
              <p className="mt-1 flex flex-wrap gap-x-2 text-base leading-tight text-ink-soft">
                {showCustomer && <span className={cn("font-semibold", tone(e, cancelled))}>{label}</span>}
                <span className="num">{fmt.format(new Date(e.created_at))}</span>
                {items && <span className="truncate">{items}</span>}
                {cancelled && <span>cancel ho gayi</span>}
              </p>
            </div>
            <span
              className={cn(
                "num w-condensed flex w-[7.5rem] shrink-0 items-center justify-end pr-5 text-[1.6rem] font-bold",
                tone(e, cancelled),
                cancelled && "line-through",
              )}
            >
              {e.amount_display}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
