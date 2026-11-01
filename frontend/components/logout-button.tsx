"use client";

import { LogOut } from "lucide-react";
import { useRouter } from "next/navigation";

export function LogoutButton() {
  const router = useRouter();
  return (
    <button type="button" aria-label="Logout"
      onClick={async () => { await fetch("/api/auth/logout", { method: "POST" }).catch(() => null); router.replace("/login"); router.refresh(); }}
      className="flex h-12 items-center gap-2 rounded-full border-2 border-rule bg-white px-4 text-base font-semibold text-ink-soft active:bg-paper">
      <LogOut className="h-5 w-5" aria-hidden /> Logout
    </button>
  );
}
