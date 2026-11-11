// Pure state machine for the one-button voice console. No browser APIs here, so it is fully
// unit-tested (vitest). The recorder/player components dispatch events into it.

export type Stage =
  | "confirm"
  | "confirm_large"
  | "disambiguate"
  | "customer"
  | "amount"
  | "done"
  | "error";

export interface Turn {
  event_id: number;
  status: "pending" | "confirmed" | "rejected" | "failed";
  stage: Stage;
  transcript: string | null;
  confirm_text: string;
  confirm_audio_url: string | null;
  needs_confirmation: boolean;
  // "Kaun se Sharma ji?" -> customers to pick from; "Do rakam suni" -> amounts to pick from.
  options: { customer_id?: number; name?: string; amount_paise?: number; label?: string }[];
  entry_id: number | null;
  balance_paise: number | null;
}

export type Phase =
  | "idle" // ready: "Dabaye rakhiye aur boliye"
  | "permission" // asking for the mic
  | "listening" // button held, recording
  | "thinking" // uploaded, waiting for the server
  | "speaking" // playing Timbre's reply
  | "awaiting" // a question is open (confirm / which customer / how much)
  | "blocked"; // mic permission denied

export interface State {
  phase: Phase;
  turn: Turn | null; // the open conversation, if any
  message: string; // what the screen says right now (Hinglish)
  committed: number; // increments on each committed entry -> refresh ledger views
}

export type Event =
  | { type: "PRESS" }
  | { type: "PERMISSION_OK" }
  | { type: "PERMISSION_DENIED" }
  | { type: "RELEASE" }
  | { type: "TOO_SHORT" }
  | { type: "RESPONSE"; turn: Turn }
  | { type: "AUDIO_ENDED" }
  | { type: "TAP"; } // user tapped ✓ / ✗ / an option -> request in flight
  | { type: "FAILED"; message: string }
  | { type: "OFFLINE" }
  | { type: "RESET" };

export const COPY = {
  idle: "Dabaye rakhiye aur boliye",
  permission: "Mic ki permission dijiye",
  listening: "Sun raha hoon…",
  thinking: "Samajh raha hoon…",
  tooShort: "Thoda lamba dabaiye aur poora boliye",
  blocked: "Mic band hai. Browser settings mein jaake is site ko mic ki permission dijiye.",
  offline: "Internet nahi hai. Thodi der baad boliye.",
  failed: "Kuch gadbad ho gayi. Dobara boliye.",
} as const;

export const initialState: State = { phase: "idle", turn: null, message: COPY.idle, committed: 0 };

const OPEN_STAGES: Stage[] = ["confirm", "confirm_large", "disambiguate", "customer", "amount"];

export function isOpen(turn: Turn | null): boolean {
  return !!turn && turn.status === "pending" && OPEN_STAGES.includes(turn.stage);
}

function afterReply(state: State, turn: Turn): State {
  const committed =
    turn.status === "confirmed" && turn.entry_id !== null ? state.committed + 1 : state.committed;
  return {
    phase: turn.confirm_audio_url ? "speaking" : isOpen(turn) ? "awaiting" : "idle",
    turn: isOpen(turn) ? turn : null,
    message: turn.confirm_text,
    committed,
  };
}

export function reducer(state: State, event: Event): State {
  switch (event.type) {
    case "PRESS":
      if (state.phase === "thinking") return state; // one request at a time
      return { ...state, phase: "permission", message: COPY.permission };
    case "PERMISSION_OK":
      return state.phase === "permission"
        ? { ...state, phase: "listening", message: COPY.listening }
        : state;
    case "PERMISSION_DENIED":
      return { ...state, phase: "blocked", message: COPY.blocked };
    case "RELEASE":
      return state.phase === "listening" ? { ...state, phase: "thinking", message: COPY.thinking } : state;
    case "TOO_SHORT":
      return { ...state, phase: isOpen(state.turn) ? "awaiting" : "idle", message: COPY.tooShort };
    case "TAP":
      return { ...state, phase: "thinking", message: COPY.thinking };
    case "RESPONSE":
      return afterReply(state, event.turn);
    case "AUDIO_ENDED":
      return state.phase === "speaking"
        ? { ...state, phase: isOpen(state.turn) ? "awaiting" : "idle" }
        : state;
    case "FAILED":
      return { ...state, phase: isOpen(state.turn) ? "awaiting" : "idle", message: event.message };
    case "OFFLINE":
      return { ...state, phase: isOpen(state.turn) ? "awaiting" : "idle", message: COPY.offline };
    case "RESET":
      return { ...initialState, committed: state.committed };
  }
}

/** Where the next recording goes: a new turn, or an answer to the open question. */
export function nextTarget(state: State): { kind: "turn" } | { kind: "confirm"; eventId: number } {
  return isOpen(state.turn) ? { kind: "confirm", eventId: state.turn!.event_id } : { kind: "turn" };
}

/** Rupees typed into the amount box -> integer paise, or null. No float arithmetic. */
export function rupeesToPaise(input: string): number | null {
  const m = input.trim().replace(/[₹,\s]/g, "").match(/^(\d{1,8})(?:\.(\d{1,2}))?$/);
  if (!m) return null;
  const paise = Number(m[1]) * 100 + Number((m[2] ?? "").padEnd(2, "0"));
  return paise > 0 ? paise : null;
}

/** wa.me link with a polite payment reminder (no WhatsApp API: the shopkeeper presses send).
 *  With no saved number WhatsApp opens its contact picker instead. */
export function reminderLink(
  customer: { display_name: string; phone: string | null; balance_paise: number },
  shopName: string | null | undefined,
): string {
  const digits = (customer.phone ?? "").replace(/\D/g, "");
  const to = digits.length === 10 ? `91${digits}` : digits.length >= 11 ? digits : "";
  const from = shopName ? `${shopName} se. ` : "";
  const text = `Namaste ${customer.display_name}, ${from}Aapka ${formatInr(customer.balance_paise)} baaki hai. Jab ho sake jama kar dijiye. Dhanyavaad.`;
  return `https://wa.me/${to}?text=${encodeURIComponent(text)}`;
}

/** 12000000 -> "₹1,20,000"; 1250 -> "₹12.50" (Indian grouping, integer maths). */
export function formatInr(paise: number): string {
  const sign = paise < 0 ? "-" : "";
  const abs = Math.abs(paise);
  const rupees = Math.floor(abs / 100).toString();
  const p = abs % 100;
  const last3 = rupees.slice(-3);
  const head = rupees.slice(0, -3).replace(/\B(?=(\d{2})+(?!\d))/g, ",");
  return `${sign}₹${head ? `${head},${last3}` : last3}${p ? `.${p.toString().padStart(2, "0")}` : ""}`;
}
