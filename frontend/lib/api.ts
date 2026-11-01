export type BackendStatus = "online" | "offline";

export interface HealthResult {
  status: BackendStatus;
  version?: string;
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
