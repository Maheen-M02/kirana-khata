import type { Entry } from "@/lib/api";
import { cn } from "@/lib/utils";

const LABEL: Record<Entry["type"], string> = {
  credit_sale: "Udhaar",
  payment_received: "Jama",
  cash_sale: "Nakad",
  adjustment: "Badlav",
};

const time = new Intl.DateTimeFormat("en-IN", {
  hour: "numeric",
  minute: "2-digit",
  day: "numeric",
  month: "short",
  timeZone: "Asia/Kolkata",
});

export function EntryList({ entries, showCustomer = true }: { entries: Entry[]; showCustomer?: boolean }) {
  if (entries.length === 0) {
    return <p className="py-6 text-center text-muted-foreground">Abhi koi entry nahi.</p>;
  }
  return (
    <ul className="divide-y rounded-2xl border">
      {entries.map((e) => {
        const cancelled = e.reversed_by !== null;
        return (
          <li key={e.id} className="flex items-center justify-between gap-3 px-4 py-3">
            <div className="min-w-0">
              <p className={cn("truncate text-base font-semibold", cancelled && "line-through opacity-60")}>
                {e.is_reversal ? "Cancel" : LABEL[e.type]}
                {showCustomer && e.customer_name ? ` · ${e.customer_name}` : ""}
              </p>
              <p className="truncate text-sm text-muted-foreground">
                {time.format(new Date(e.created_at))}
                {e.lines.length > 0 && ` · ${e.lines.map((l) => l.item_name).join(", ")}`}
                {cancelled && " · cancel ho gayi"}
              </p>
            </div>
            <span
              className={cn(
                "shrink-0 text-lg font-bold tabular-nums",
                e.is_reversal || cancelled ? "text-muted-foreground" :
                  e.type === "payment_received" ? "text-green-700" :
                  e.type === "credit_sale" ? "text-red-700" : "",
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
