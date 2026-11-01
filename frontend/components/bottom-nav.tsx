import { BookOpen, Mic } from "lucide-react";
import Link from "next/link";

import { cn } from "@/lib/utils";

export function BottomNav({ active }: { active: "home" | "customers" }) {
  const tabs = [
    { key: "home", href: "/", label: "Bolo", Icon: Mic },
    { key: "customers", href: "/customers", label: "Khate", Icon: BookOpen },
  ] as const;
  return (
    <nav aria-label="Main" className="pb-safe fixed inset-x-0 bottom-0 z-20 border-t border-rule bg-paper/95 backdrop-blur">
      <div className="mx-auto flex max-w-md">
        {tabs.map(({ key, href, label, Icon }) => {
          const on = active === key;
          return (
            <Link
              key={key}
              href={href}
              aria-current={on ? "page" : undefined}
              className={cn(
                "relative flex h-[4.25rem] flex-1 flex-col items-center justify-center gap-0.5 text-base font-semibold",
                on ? "text-ink" : "text-ink-soft",
              )}
            >
              <span aria-hidden className={cn("absolute top-0 h-1 w-12 rounded-b-full", on ? "bg-marigold" : "bg-transparent")} />
              <Icon className="h-6 w-6" strokeWidth={on ? 2.5 : 2} aria-hidden />
              {label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
