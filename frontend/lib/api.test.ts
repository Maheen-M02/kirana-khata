import { describe, expect, it, vi } from "vitest";

import { getHealth } from "./api";

const asFetch = (impl: (...args: unknown[]) => Promise<Response>) =>
  vi.fn(impl) as unknown as typeof fetch;

describe("getHealth", () => {
  it("reports online with version when backend says ok", async () => {
    const f = asFetch(async () => Response.json({ status: "ok", version: "0.1.0" }));
    await expect(getHealth("http://x", f)).resolves.toEqual({ status: "online", version: "0.1.0" });
    expect(f).toHaveBeenCalledWith("http://x/api/health", expect.objectContaining({ cache: "no-store" }));
  });

  it("reports offline on non-2xx", async () => {
    const f = asFetch(async () => new Response("nope", { status: 503 }));
    await expect(getHealth("http://x", f)).resolves.toEqual({ status: "offline" });
  });

  it("reports offline on unexpected body", async () => {
    const f = asFetch(async () => Response.json({ hello: "world" }));
    await expect(getHealth("http://x", f)).resolves.toEqual({ status: "offline" });
  });

  it("never throws on network error", async () => {
    const f = asFetch(async () => {
      throw new TypeError("fetch failed");
    });
    await expect(getHealth("http://x", f)).resolves.toEqual({ status: "offline" });
  });
});
