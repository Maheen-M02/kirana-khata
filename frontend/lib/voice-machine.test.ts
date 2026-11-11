import { describe, expect, it } from "vitest";

import {
  COPY,
  formatInr,
  initialState,
  nextTarget,
  reducer,
  reminderLink,
  rupeesToPaise,
  type Event,
  type State,
  type Turn,
} from "./voice-machine";

const turn = (over: Partial<Turn> = {}): Turn => ({
  event_id: 7,
  status: "pending",
  stage: "confirm",
  transcript: "Sharma ji ne ek sau bees udhaar",
  confirm_text: "Ramesh Sharma, ek sau bees rupaye udhaar. Sahi hai?",
  confirm_audio_url: "/api/voice/audio/abc.mp3",
  needs_confirmation: true,
  options: [],
  entry_id: null,
  balance_paise: null,
  ...over,
});

const run = (events: Event[], from: State = initialState) => events.reduce(reducer, from);

describe("voice state machine", () => {
  it("hold -> listen -> release -> think", () => {
    const s = run([{ type: "PRESS" }, { type: "PERMISSION_OK" }, { type: "RELEASE" }]);
    expect(s.phase).toBe("thinking");
    expect(s.message).toBe(COPY.thinking);
  });

  it("speaks the confirmation, then waits for haan/nahi", () => {
    let s = run([{ type: "PRESS" }, { type: "PERMISSION_OK" }, { type: "RELEASE" },
      { type: "RESPONSE", turn: turn() }]);
    expect(s.phase).toBe("speaking");
    expect(s.message).toMatch(/Sahi hai\?$/);
    s = reducer(s, { type: "AUDIO_ENDED" });
    expect(s.phase).toBe("awaiting");
    expect(nextTarget(s)).toEqual({ kind: "confirm", eventId: 7 });
  });

  it("no audio (TTS down) goes straight to awaiting with the text", () => {
    const s = reducer({ ...initialState, phase: "thinking" },
      { type: "RESPONSE", turn: turn({ confirm_audio_url: null }) });
    expect(s.phase).toBe("awaiting");
    expect(s.message).toMatch(/Sahi hai/);
  });

  it("a commit closes the conversation and bumps the refresh counter", () => {
    const open = reducer({ ...initialState, phase: "thinking" }, { type: "RESPONSE", turn: turn() });
    const done = reducer({ ...open, phase: "thinking" }, {
      type: "RESPONSE",
      turn: turn({ status: "confirmed", stage: "done", entry_id: 42, balance_paise: 12000,
        confirm_text: "Likh diya.", confirm_audio_url: null }),
    });
    expect(done.turn).toBeNull();
    expect(done.committed).toBe(1);
    expect(done.phase).toBe("idle");
    expect(nextTarget(done)).toEqual({ kind: "turn" });
  });

  it("queries answer without counting as a commit", () => {
    const s = reducer({ ...initialState, phase: "thinking" }, {
      type: "RESPONSE",
      turn: turn({ status: "confirmed", stage: "done", entry_id: null, confirm_audio_url: null }),
    });
    expect(s.committed).toBe(0);
  });

  it("mic denied explains how to fix it", () => {
    const s = run([{ type: "PRESS" }, { type: "PERMISSION_DENIED" }]);
    expect(s.phase).toBe("blocked");
    expect(s.message).toContain("permission");
  });

  it("an accidental tap does not lose the open question", () => {
    const open = reducer({ ...initialState, phase: "thinking" },
      { type: "RESPONSE", turn: turn({ confirm_audio_url: null }) });
    const s = run([{ type: "PRESS" }, { type: "PERMISSION_OK" }, { type: "TOO_SHORT" }], open);
    expect(s.phase).toBe("awaiting");
    expect(s.turn?.event_id).toBe(7);
    expect(s.message).toBe(COPY.tooShort);
  });

  it("ignores a second press while a request is in flight", () => {
    const thinking = { ...initialState, phase: "thinking" as const };
    expect(reducer(thinking, { type: "PRESS" })).toBe(thinking);
  });

  it("offline and failures are friendly and keep the open question", () => {
    const open = { ...initialState, phase: "thinking" as const, turn: turn() };
    expect(reducer(open, { type: "OFFLINE" }).message).toBe(COPY.offline);
    expect(reducer(open, { type: "FAILED", message: "x" }).phase).toBe("awaiting");
  });
});

describe("money helpers (integer paise only)", () => {
  it.each([
    ["120", 12000], ["₹1,200", 120000], ["12.5", 1250], ["12.05", 1205], [" 99 ", 9900],
  ])("rupeesToPaise(%s) = %d", (input, paise) => {
    expect(rupeesToPaise(input)).toBe(paise);
  });

  it.each(["", "0", "abc", "12.345", "-5", "1e3"])("rejects %s", (input) => {
    expect(rupeesToPaise(input)).toBeNull();
  });

  it.each([
    [12000000, "₹1,20,000"], [1250, "₹12.50"], [-500, "-₹5"], [100, "₹1"], [0, "₹0"],
    [99999999, "₹9,99,999.99"],
  ])("formatInr(%d) = %s", (paise, text) => {
    expect(formatInr(paise)).toBe(text);
  });
});

describe("reminderLink", () => {
  const c = { display_name: "Anil Gupta", phone: "98765 43210", balance_paise: 32000 };
  it("addresses a saved 10-digit number with the India code", () => {
    const url = reminderLink(c, "Ramesh Kirana Store");
    expect(url.startsWith("https://wa.me/919876543210?text=")).toBe(true);
    expect(decodeURIComponent(url.split("text=")[1])).toBe(
      "Namaste Anil Gupta, Ramesh Kirana Store se. Aapka ₹320 baaki hai. Jab ho sake jama kar dijiye. Dhanyavaad.",
    );
  });
  it("opens the contact picker when no number is saved", () => {
    expect(reminderLink({ ...c, phone: null }, null).startsWith("https://wa.me/?text=")).toBe(true);
  });
});
