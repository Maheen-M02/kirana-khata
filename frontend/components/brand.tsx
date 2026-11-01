import { cn } from "@/lib/utils";

/** App mark: a marigold mic on ink, same as the home-screen icon. */
export function BrandMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 64" aria-hidden className={cn("h-10 w-10", className)}>
      <rect width="64" height="64" rx="16" fill="hsl(var(--ink))" />
      <rect x="25" y="12" width="14" height="25" rx="7" fill="hsl(var(--marigold))" />
      <path d="M18 31a14 14 0 0 0 28 0" fill="none" stroke="hsl(var(--marigold))" strokeWidth="4" strokeLinecap="round" />
      <path d="M32 45v7" stroke="hsl(var(--marigold))" strokeWidth="4" strokeLinecap="round" />
    </svg>
  );
}

export function Wordmark({ className }: { className?: string }) {
  return (
    <span className={cn("flex items-center gap-2.5", className)}>
      <BrandMark className="h-9 w-9" />
      <span className="w-wide text-xl font-bold leading-none tracking-tight">Kirana Khata</span>
    </span>
  );
}
