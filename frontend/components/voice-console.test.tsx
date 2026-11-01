import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { VoiceConsole } from "./voice-console";

const refresh = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh }) }));

class FakeRecorder {
  static isTypeSupported = (m: string) => m.startsWith("audio/webm");
  state: "inactive" | "recording" = "inactive";
  mimeType = "audio/webm;codecs=opus";
  ondataavailable: ((e: { data: Blob }) => void) | null = null;
  onstop: (() => void) | null = null;
  start() { this.state = "recording"; }
  stop() {
    this.state = "inactive";
    this.ondataavailable?.({ data: new Blob(["opus"], { type: this.mimeType }) });
    this.onstop?.();
  }
}

const turn = (over: Record<string, unknown> = {}) => ({
  event_id: 5, status: "pending", stage: "confirm", transcript: "Sharma ji 120 udhaar",
  confirm_text: "Ramesh Sharma, ek sau bees rupaye udhaar. Sahi hai?", confirm_audio_url: null,
  needs_confirmation: true, options: [], entry_id: null, balance_paise: null, ...over,
});

let now = 1_000_000;
const json = (body: unknown) => Promise.resolve(new Response(JSON.stringify(body), { status: 200 }));

beforeEach(() => {
  vi.stubGlobal("MediaRecorder", FakeRecorder);
  vi.spyOn(Date, "now").mockImplementation(() => now);
  Object.defineProperty(navigator, "mediaDevices", {
    configurable: true,
    value: { getUserMedia: vi.fn().mockResolvedValue({ getTracks: () => [{ stop: vi.fn() }] }) },
  });
});
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); refresh.mockClear(); });

async function holdAndRelease(ms: number) {
  const mic = screen.getByRole("button", { name: /dabaye rakhiye/i });
  await act(async () => { fireEvent.pointerDown(mic, { pointerId: 1 }); });
  await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Sun raha hoon"));
  now += ms;
  await act(async () => { fireEvent.pointerUp(mic, { pointerId: 1 }); });
}

describe("VoiceConsole", () => {
  it("hold, speak, confirm with Haan -> entry committed and ledger refreshed", async () => {
    const fetchMock = vi.fn()
      .mockImplementationOnce(() => json(turn()))
      .mockImplementationOnce(() => json(turn({ status: "confirmed", stage: "done", entry_id: 9,
        balance_paise: 12000, confirm_text: "Likh diya. Ramesh Sharma ka total baaki ek sau bees rupaye." })));
    vi.stubGlobal("fetch", fetchMock);
    render(<VoiceConsole />);

    await holdAndRelease(1500);
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Sahi hai?"));
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/voice/turn");
    expect((init.headers as Record<string, string>)["Idempotency-Key"]).toMatch(/^[0-9a-f-]{36}$/);
    expect(init.body).toBeInstanceOf(FormData);
    expect(screen.getByText(/Aapne kaha/)).toHaveTextContent("Sharma ji 120 udhaar");

    await act(async () => { fireEvent.click(screen.getByRole("button", { name: /haan/i })); });
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Likh diya."));
    expect(fetchMock.mock.calls[1][0]).toBe("/api/voice/5/confirm");
    expect(JSON.parse(fetchMock.mock.calls[1][1].body as string)).toEqual({ accept: true });
    expect(refresh).toHaveBeenCalled();
    expect(screen.queryByRole("button", { name: /nahi/i })).toBeNull();
  });

  it("a 0.2 s tap is not sent (no credits spent)", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    render(<VoiceConsole />);
    await holdAndRelease(200);
    expect(screen.getByRole("status")).toHaveTextContent("Thoda lamba dabaiye");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("mic permission denied shows how to fix it", async () => {
    (navigator.mediaDevices.getUserMedia as ReturnType<typeof vi.fn>).mockRejectedValueOnce(new Error("denied"));
    render(<VoiceConsole />);
    await act(async () => { fireEvent.pointerDown(screen.getByRole("button", { name: /dabaye/i }), { pointerId: 1 }); });
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Mic band hai"));
  });

  it("disambiguation options are tappable", async () => {
    const fetchMock = vi.fn()
      .mockImplementationOnce(() => json(turn({ stage: "disambiguate", needs_confirmation: false,
        confirm_text: "Kaun se Sharma ji: Ramesh ya Suresh?",
        options: [{ customer_id: 1, name: "Ramesh Sharma" }, { customer_id: 2, name: "Suresh Sharma" }] })))
      .mockImplementationOnce(() => json(turn({ confirm_text: "Suresh Sharma, ek sau bees rupaye udhaar. Sahi hai?" })));
    vi.stubGlobal("fetch", fetchMock);
    render(<VoiceConsole />);
    await holdAndRelease(1200);
    await act(async () => { fireEvent.click(await screen.findByRole("button", { name: "Suresh Sharma" })); });
    expect(JSON.parse(fetchMock.mock.calls[1][1].body as string)).toEqual({ customer_id: 2 });
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Suresh Sharma, ek sau bees"));
  });

  it("server errors show the friendly Hinglish message, never a raw error", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(new Response(
      JSON.stringify({ error: { code: "x", message: "Ek second rukiye, phir boliye." } }), { status: 503 }))));
    render(<VoiceConsole />);
    await holdAndRelease(1000);
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Ek second rukiye, phir boliye."));
  });
});
