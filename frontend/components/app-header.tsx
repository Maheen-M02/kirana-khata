import { BrandMark } from "@/components/brand";
import { cn } from "@/lib/utils";

const DAYS = ["Ravivar", "Somvar", "Mangalvar", "Budhvar", "Guruvar", "Shukravar", "Shanivar"];

/** "Ravivar, 1 Nov" in IST, whatever the server's clock zone is. */
export function todayLabel(now: Date = new Date()): string {
  const parts = new Intl.DateTimeFormat("en-IN", {
    timeZone: "Asia/Kolkata",
    weekday: "short",
    day: "numeric",
    month: "short",
  }).formatToParts(now);
  const get = (t: string) => parts.find((p) => p.type === t)?.value ?? "";
  const idx = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].indexOf(get("weekday"));
  return `${DAYS[idx] ?? get("weekday")}, ${get("day")} ${get("month")}`;
}

export function AppHeader({
  shopName,
  offline,
  right,
}: {
  shopName?: string | null;
  offline?: boolean;
  right?: React.ReactNode;
}) {
  return (
    <header className="flex items-center gap-3">
      <BrandMark className="h-11 w-11 shrink-0" />
      <div className="min-w-0 flex-1">
        <p className="truncate text-xl font-bold leading-tight">{shopName ?? "Kirana Khata"}</p>
        <p className="text-base leading-tight text-ink-soft">{todayLabel()}</p>
      </div>
      {offline && (
        <span role="alert" className={cn("shrink-0 rounded-full bg-udhaar px-3 py-1.5 text-base font-semibold text-white")}>
          Server band hai
        </span>
      )}
      {right}
    </header>
  );
}
