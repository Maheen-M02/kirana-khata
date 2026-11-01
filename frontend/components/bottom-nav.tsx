import { Mic, Users } from "lucide-react";
import Link from "next/link";

export function BottomNav({ active }: { active: "home" | "customers" }) {
  const item = "flex h-16 flex-1 flex-col items-center justify-center gap-1 text-sm font-semibold";
  return (
    <nav aria-label="Main" className="fixed inset-x-0 bottom-0 z-10 border-t bg-background/95 backdrop-blur">
      <div className="mx-auto flex max-w-md">
        <Link href="/" aria-current={active === "home" ? "page" : undefined}
          className={`${item} ${active === "home" ? "text-primary" : "text-muted-foreground"}`}>
          <Mic className="h-6 w-6" aria-hidden /> Bolo
        </Link>
        <Link href="/customers" aria-current={active === "customers" ? "page" : undefined}
          className={`${item} ${active === "customers" ? "text-primary" : "text-muted-foreground"}`}>
          <Users className="h-6 w-6" aria-hidden /> Khate
        </Link>
      </div>
    </nav>
  );
}
