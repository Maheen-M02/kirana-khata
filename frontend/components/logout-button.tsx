"use client";

import { LogOut } from "lucide-react";
import { useRouter } from "next/navigation";

export function LogoutButton() {
  const router = useRouter();
  return (
    <button type="button" aria-label="Logout"
      onClick={async () => { await fetch("/api/auth/logout", { method: "POST" }).catch(() => null); router.replace("/login"); router.refresh(); }}
      className="flex h-12 w-12 items-center justify-center rounded-full text-muted-foreground">
      <LogOut className="h-6 w-6" aria-hidden />
    </button>
  );
}
