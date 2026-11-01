// Server-side data access (server components). The browser uses same-origin /api via the
// Next.js rewrite instead (see lib/voice-api.ts).

export type BackendStatus = "online" | "offline";

export interface HealthResult {
  status: BackendStatus;
  version?: string;
}

export interface Entry {
  id: number;
  type: "credit_sale" | "cash_sale" | "payment_received" | "adjustment";
  amount_paise: number;
  amount_display: string;
  customer_id: number | null;
  customer_name: string | null;
  note: string | null;
  created_at: string;
  is_reversal: boolean;
  reverses_entry_id: number | null;
  reversed_by: number | null;
  lines: { item_name: string; qty: string | null; unit: string | null }[];
}

export interface Customer {
  id: number;
  display_name: string;
  aliases: string[];
  phone: string | null;
  balance_paise: number;
  balance_display: string;
  last_activity: string | null;
}

export interface CustomerDetail extends Customer {
  entries: Entry[];
}

export interface Sales {
  total_paise: number;
  total_display: string;
  entries: number;
  payments_paise: number;
}

export function backendUrl(): string {
  return process.env.BACKEND_URL ?? "http://localhost:8000";
}

function isHealthBody(x: unknown): x is { status: "ok"; version?: string } {
  return typeof x === "object" && x !== null && (x as { status?: unknown }).status === "ok";
}

/** Server-side health probe. Never throws: any failure is reported as "offline". */
export async function getHealth(
  baseUrl: string = backendUrl(),
  fetchImpl: typeof fetch = fetch,
): Promise<HealthResult> {
  try {
    const res = await fetchImpl(`${baseUrl}/api/health`, {
      cache: "no-store",
      signal: AbortSignal.timeout(2000),
    });
    if (!res.ok) return { status: "offline" };
    const body: unknown = await res.json();
    return isHealthBody(body) ? { status: "online", version: body.version } : { status: "offline" };
  } catch {
    return { status: "offline" };
  }
}

/** GET JSON from the backend; null on any failure so pages render a friendly empty state. */
export async function getJson<T>(path: string, fetchImpl: typeof fetch = fetch): Promise<T | null> {
  try {
    const res = await fetchImpl(`${backendUrl()}/api${path}`, {
      cache: "no-store",
      signal: AbortSignal.timeout(4000),
    });
    return res.ok ? ((await res.json()) as T) : null;
  } catch {
    return null;
  }
}
