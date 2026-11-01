"""The voice loop (MASTER_PROMPT §6): audio -> Prisma -> NLU -> resolve -> Timbre -> confirm.

State machine on `voice_event.pending_json["stage"]`:
  confirm        waiting for "haan"/"nahi" (or ✓/✗)            -> commit / reject
  confirm_large  > ₹50,000: one extra "haan" before `confirm`
  disambiguate   "Kaun se Sharma ji: Ramesh ya Suresh?"        -> name or tap -> confirm
  customer       money heard but no name                       -> name -> confirm
  amount         "Sharma ji ka kitne rupaye?"                   -> amount -> confirm
Nothing is written to the ledger except on an explicit accept in stage `confirm`.
Every turn persists a voice_event with transcript, NLU JSON, per-stage latency and status.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.ledger import queries
from app.ledger import service as svc
from app.ledger.models import Customer, EntryType, VoiceEvent, VoiceStatus, utcnow
from app.nlu import templates as tpl
from app.nlu.numbers_hi import parse_amount
from app.nlu.parser import IntentParser
from app.nlu.resolver import (
    CustomerRef,
    disambiguation_question,
    display_spoken,
    new_alias,
    resolve,
    score,
)
from app.nlu.rules import parse_rules
from app.nlu.schema import LARGE_AMOUNT_PAISE, MONEY_INTENTS, NluContext, ParsedIntent
from app.voice.audio import AudioError, prepare_audio
from app.voice.errors import GnaniError
from app.voice.gnani_stt import SpeechToText
from app.voice.gnani_tts import TextToSpeech

log = get_logger(__name__)

Stage = Literal["confirm", "confirm_large", "disambiguate", "customer", "amount", "done", "error"]
PENDING_TTL = timedelta(minutes=10)
EMPTY_TRANSCRIPT = "Awaaz saaf nahi aayi, dobara boliye."
NOTHING_PENDING = "Abhi koi entry haan ke liye baaki nahi hai. Pehle entry boliye."
EXPIRED = "Yeh entry purani ho gayi. Dobara boliye."
ASK_CUSTOMER = "Kis customer ka hai? Naam boliye."
VOICE_DOWN = "Awaaz service abhi chalu nahi hai. Thodi der baad koshish kijiye."


@dataclass
class TurnResult:
    """Response contract: {event_id, transcript, intent, confirm_text, confirm_audio_url,
    needs_confirmation} plus stage/options/balance for the UI."""

    event_id: int
    status: str
    stage: Stage
    transcript: str | None
    intent: dict[str, Any] | None
    confirm_text: str
    confirm_audio_url: str | None
    needs_confirmation: bool
    options: list[dict[str, Any]] = field(default_factory=list)
    entry_id: int | None = None
    customer_id: int | None = None
    balance_paise: int | None = None
    latency_ms: dict[str, int] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return dict(self.__dict__)


@dataclass
class VoiceTurnService:
    db: Session
    stt: SpeechToText | None
    tts: TextToSpeech | None
    parser: IntentParser
    audio_dir: Path
    tts_voice_key: str = "default"  # model+voice+language, so cached audio follows voice changes

    # ------------------------------------------------------------------ helpers
    def _customers(self, shop_id: int) -> list[CustomerRef]:
        rows = self.db.scalars(select(Customer).where(Customer.shop_id == shop_id)).all()
        return [CustomerRef(c.id, c.display_name, tuple(c.aliases)) for c in rows]

    async def _speak(self, text: str) -> tuple[str | None, int]:
        """TTS through the single-flight Gnani gate; cached on disk; never fatal."""
        if self.tts is None:
            return None, 0
        key = hashlib.sha256(f"{self.tts_voice_key}|{text}".encode()).hexdigest()
        path = self.audio_dir / "tts" / f"{key}.mp3"
        t0 = time.perf_counter()
        if not path.exists():
            try:
                audio = (await self.tts.synthesize(text)).audio
            except GnaniError as e:
                log.warning("tts_failed", kind=e.kind)
                return None, round((time.perf_counter() - t0) * 1000)
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_bytes(audio)
            tmp.replace(path)
        return f"/api/voice/audio/{key}.mp3", round((time.perf_counter() - t0) * 1000)

    async def _finish(
        self,
        event: VoiceEvent,
        *,
        status: VoiceStatus,
        stage: Stage,
        text: str,
        parsed: ParsedIntent | None = None,
        pending: dict[str, Any] | None = None,
        options: list[dict[str, Any]] | None = None,
        entry_id: int | None = None,
        customer_id: int | None = None,
        balance: int | None = None,
        t_start: float | None = None,
    ) -> TurnResult:
        url, tts_ms = await self._speak(text)
        event.latency_tts_ms = (event.latency_tts_ms or 0) + tts_ms
        if t_start is not None:
            event.latency_total_ms = round((time.perf_counter() - t_start) * 1000)
        event.status = status
        event.pending_json = pending
        result = TurnResult(
            event_id=event.id,
            status=status.value,
            stage=stage,
            transcript=event.transcript,
            intent=event.nlu_json,
            confirm_text=text,
            confirm_audio_url=url,
            needs_confirmation=stage in ("confirm", "confirm_large"),
            options=options or [],
            entry_id=entry_id,
            customer_id=customer_id,
            balance_paise=balance,
            latency_ms={
                k: v
                for k, v in {
                    "stt": event.latency_stt_ms,
                    "nlu": event.latency_nlu_ms,
                    "tts": event.latency_tts_ms,
                    "total": event.latency_total_ms,
                }.items()
                if v is not None
            },
        )
        event.response_json = result.to_json()
        self.db.commit()
        log.info(
            "voice_turn",
            event_id=event.id,
            status=status.value,
            stage=stage,
            intent=(parsed.intent if parsed else None),
            latency=result.latency_ms,
        )
        return result

    async def _transcribe(self, event: VoiceEvent, audio: bytes) -> str:
        if self.stt is None:
            raise GnaniError("auth", "STT not configured")
        prepared = await prepare_audio(audio)
        event.duration_ms = prepared.duration_ms
        wav_path = self.audio_dir / "in" / f"{event.id}.wav"
        wav_path.parent.mkdir(parents=True, exist_ok=True)
        wav_path.write_bytes(prepared.wav)
        event.audio_path = str(wav_path)
        r = await self.stt.transcribe(prepared.wav, request_id=f"kk-{event.id}")
        event.latency_stt_ms = r.latency_ms
        event.stt_model, event.stt_request_id = r.model, r.request_id
        event.detected_lang = r.detected_language
        return r.transcript

    # ------------------------------------------------------------------ /voice/turn
    async def handle_turn(
        self,
        shop_id: int,
        *,
        audio: bytes | None = None,
        transcript: str | None = None,
        idempotency_key: str | None = None,
    ) -> TurnResult:
        if idempotency_key:
            prior = self.db.scalar(
                select(VoiceEvent).where(
                    VoiceEvent.shop_id == shop_id, VoiceEvent.idempotency_key == idempotency_key
                )
            )
            if prior is not None and prior.response_json and "event_id" in prior.response_json:
                return TurnResult(**prior.response_json)  # double tap / retry: same answer
        t0 = time.perf_counter()
        event = VoiceEvent(
            shop_id=shop_id,
            idempotency_key=idempotency_key,
            status=VoiceStatus.pending,
            created_at=utcnow(),
        )
        self.db.add(event)
        try:
            self.db.flush()
        except IntegrityError:  # two concurrent requests with the same key
            self.db.rollback()
            prior = self.db.scalar(
                select(VoiceEvent).where(
                    VoiceEvent.shop_id == shop_id, VoiceEvent.idempotency_key == idempotency_key
                )
            )
            if prior is not None and prior.response_json and "event_id" in prior.response_json:
                return TurnResult(**prior.response_json)
            raise
        try:
            if transcript is None:
                if audio is None:
                    raise AudioError("too_short", "no audio")
                transcript = await self._transcribe(event, audio)
            else:
                event.latency_stt_ms = 0
            event.transcript = transcript
            if not transcript.strip():
                event.error = "empty_transcript"
                return await self._finish(
                    event,
                    status=VoiceStatus.failed,
                    stage="error",
                    text=EMPTY_TRANSCRIPT,
                    t_start=t0,
                )
            customers = self._customers(shop_id)
            known = [n for c in customers for n in c.names]
            t_nlu = time.perf_counter()
            parsed = await self.parser.parse(transcript, NluContext(known_customers=known))
            event.latency_nlu_ms = round((time.perf_counter() - t_nlu) * 1000)
            event.nlu_json = parsed.model_dump(mode="json")
            event.nlu_source, event.confidence = parsed.source, parsed.confidence
            return await self._route(shop_id, event, parsed, customers, t0)
        except AudioError as e:
            event.error = f"audio:{e.reason}"
            return await self._finish(
                event, status=VoiceStatus.failed, stage="error", text=e.user_message, t_start=t0
            )
        except GnaniError as e:
            event.error = f"gnani:{e.kind}"
            text = VOICE_DOWN if e.kind == "auth" else e.user_message
            return await self._finish(
                event, status=VoiceStatus.failed, stage="error", text=text, t_start=t0
            )

    async def _route(
        self,
        shop_id: int,
        event: VoiceEvent,
        parsed: ParsedIntent,
        customers: list[CustomerRef],
        t0: float,
    ) -> TurnResult:
        intent = parsed.intent
        if intent in ("confirm_yes", "confirm_no"):
            return await self._route_bare_yes_no(shop_id, event, parsed, t0)
        if intent == "query_sales_today":
            s = queries.sales_summary(self.db, shop_id)
            return await self._finish(
                event,
                status=VoiceStatus.confirmed,
                stage="done",
                text=tpl.sales_today_text(s.total_paise, s.entries),
                parsed=parsed,
                t_start=t0,
            )
        if intent == "query_dues_list":
            owing = queries.dues(self.db, shop_id, limit=3)
            text = tpl.dues_list_text([(b.display_name, b.balance_paise) for b in owing])
            return await self._finish(
                event,
                status=VoiceStatus.confirmed,
                stage="done",
                text=text,
                parsed=parsed,
                t_start=t0,
            )
        if intent == "undo_last":
            pending: dict[str, Any] = {"stage": "confirm", "intent": "undo_last"}
            return await self._finish(
                event,
                status=VoiceStatus.pending,
                stage="confirm",
                text=tpl.UNDO_CONFIRM,
                parsed=parsed,
                pending=pending,
                t_start=t0,
            )
        if intent == "query_balance":
            res = resolve(parsed.customer, customers)
            if res.kind == "matched" and res.customer:
                bal = queries.customer_balance(self.db, shop_id, res.customer.id)
                return await self._finish(
                    event,
                    status=VoiceStatus.confirmed,
                    stage="done",
                    text=tpl.balance_text(res.customer.display_name, bal),
                    parsed=parsed,
                    customer_id=res.customer.id,
                    balance=bal,
                    t_start=t0,
                )
            if res.kind == "ambiguous":
                pending = {
                    "stage": "disambiguate",
                    "intent": intent,
                    "candidates": [c.customer.id for c in res.candidates],
                }
                return await self._finish(
                    event,
                    status=VoiceStatus.pending,
                    stage="disambiguate",
                    text=res.question or tpl.UNKNOWN,
                    parsed=parsed,
                    pending=pending,
                    options=_options(res.candidates),
                    t_start=t0,
                )
            name = display_spoken(parsed.customer) if parsed.customer else "Is naam"
            return await self._finish(
                event,
                status=VoiceStatus.failed,
                stage="error",
                text=f"{name} ka koi khata nahi mila.",
                parsed=parsed,
                t_start=t0,
            )
        if intent in MONEY_INTENTS:
            pending = self._money_pending(parsed, customers)
            return await self._respond_pending(event, pending, parsed, customers, t0)
        event.error = "nlu_unknown"
        return await self._finish(
            event,
            status=VoiceStatus.failed,
            stage="error",
            text=tpl.UNKNOWN,
            parsed=parsed,
            t_start=t0,
        )

    def _money_pending(self, parsed: ParsedIntent, customers: list[CustomerRef]) -> dict[str, Any]:
        pending: dict[str, Any] = {
            "intent": parsed.intent,
            "amount_paise": parsed.amount_paise,
            "customer_id": None,
            "new_customer": None,
            "spoken_customer": parsed.customer,
            "candidates": [],
            "flags": parsed.flags,
            "items": [i.model_dump(mode="json") for i in parsed.items],
        }
        needs_customer = parsed.intent != "cash_sale"
        if needs_customer and parsed.customer:
            res = resolve(parsed.customer, customers)
            if res.kind == "matched" and res.customer:
                pending["customer_id"] = res.customer.id
            elif res.kind == "ambiguous":
                pending["candidates"] = [c.customer.id for c in res.candidates]
                pending["stage"] = "disambiguate"
                return pending
            else:
                pending["new_customer"] = display_spoken(parsed.customer)
        elif needs_customer:
            pending["stage"] = "customer"
            return pending
        pending["stage"] = "amount" if parsed.amount_paise is None else self._confirm_stage(pending)
        return pending

    @staticmethod
    def _confirm_stage(pending: dict[str, Any]) -> str:
        amt = pending.get("amount_paise") or 0
        if amt > LARGE_AMOUNT_PAISE and not pending.get("large_ok"):
            return "confirm_large"
        return "confirm"

    def _name_for(self, pending: dict[str, Any]) -> str | None:
        if pending.get("customer_id"):
            c = self.db.get(Customer, pending["customer_id"])
            return c.display_name if c else None
        return pending.get("new_customer")

    async def _respond_pending(
        self,
        event: VoiceEvent,
        pending: dict[str, Any],
        parsed: ParsedIntent | None,
        customers: list[CustomerRef],
        t0: float | None,
    ) -> TurnResult:
        stage: Stage = pending["stage"]
        options: list[dict[str, Any]] = []
        if stage == "disambiguate":
            refs = [c for c in customers if c.id in pending["candidates"]]
            text = disambiguation_question(pending.get("spoken_customer") or "customer", refs)
            options = [{"customer_id": c.id, "name": c.display_name} for c in refs]
        elif stage == "customer":
            text = ASK_CUSTOMER
        elif stage == "amount":
            name = self._name_for(pending)
            who = f"{name} ka" if name else ""
            text = f"{who} kitne rupaye?" if who else "Kitne rupaye?"  # keep name casing
        else:
            intent_obj = ParsedIntent(
                intent=pending["intent"],
                amount_paise=pending["amount_paise"],
                confidence=1.0,
                source="rules",
                flags=pending.get("flags", []),
            )
            name = self._name_for(pending)
            text = tpl.confirm_text(intent_obj, name)
            if pending.get("new_customer") and not pending.get("customer_id"):
                text = f"Naya customer {pending['new_customer']}. {text}"
            if stage == "confirm_large":
                text = f"{text} Bada amount hai, pakka?"
        return await self._finish(
            event,
            status=VoiceStatus.pending,
            stage=stage,
            text=text,
            parsed=parsed,
            pending=pending,
            options=options,
            t_start=t0,
        )

    async def _route_bare_yes_no(
        self, shop_id: int, event: VoiceEvent, parsed: ParsedIntent, t0: float
    ) -> TurnResult:
        """Hands-free: a "haan" sent as a new turn confirms the latest open question."""
        open_event = self.db.scalar(
            select(VoiceEvent)
            .where(
                VoiceEvent.shop_id == shop_id,
                VoiceEvent.status == VoiceStatus.pending,
                VoiceEvent.id != event.id,
                VoiceEvent.created_at >= utcnow() - PENDING_TTL,
            )
            .order_by(VoiceEvent.id.desc())
            .limit(1)
        )
        if open_event is None:
            return await self._finish(
                event,
                status=VoiceStatus.failed,
                stage="error",
                text=NOTHING_PENDING,
                parsed=parsed,
                t_start=t0,
            )
        event.status, event.pending_json = VoiceStatus.confirmed, None
        self.db.flush()
        result = await self.handle_confirm(
            shop_id, open_event.id, accept=parsed.intent == "confirm_yes"
        )
        event.response_json = result.to_json()  # replaying this turn returns the same answer
        self.db.commit()
        return result

    # ------------------------------------------------------------------ /voice/{id}/confirm
    async def handle_confirm(
        self,
        shop_id: int,
        event_id: int,
        *,
        accept: bool | None = None,
        customer_id: int | None = None,
        amount_paise: int | None = None,
        audio: bytes | None = None,
        transcript: str | None = None,
    ) -> TurnResult:
        event = self.db.get(VoiceEvent, event_id)
        if event is None or event.shop_id != shop_id:
            raise svc.LedgerError("event_not_found", "Yeh baat nahi mili. Dobara boliye.", 404)
        if event.status != VoiceStatus.pending or not event.pending_json:
            if event.response_json and "event_id" in event.response_json:
                return TurnResult(**event.response_json)  # already handled: idempotent
            raise svc.LedgerError("not_pending", "Isme kuch confirm karna baaki nahi.", 409)
        if utcnow() - event.created_at > PENDING_TTL:
            event.error = "expired"
            return await self._finish(
                event, status=VoiceStatus.rejected, stage="error", text=EXPIRED
            )
        pending = dict(event.pending_json)
        stage = pending["stage"]
        customers = self._customers(shop_id)
        try:
            if audio is not None and transcript is None:
                transcript = await self._transcribe(event, audio)
        except (AudioError, GnaniError) as e:
            msg = e.user_message
            return await self._finish(
                event, status=VoiceStatus.pending, stage=stage, text=msg, pending=pending
            )

        if stage in ("disambiguate", "customer"):
            chosen = self._choose_customer(pending, customers, customer_id, transcript)
            if chosen is None:
                if accept is False or (
                    transcript and parse_rules(transcript).intent == "confirm_no"
                ):
                    return await self._reject(event)
                return await self._respond_pending(event, pending, None, customers, None)
            pending.update(chosen)
            if pending["intent"] == "query_balance":
                bal = queries.customer_balance(self.db, shop_id, pending["customer_id"])
                name = self._name_for(pending) or ""
                return await self._finish(
                    event,
                    status=VoiceStatus.confirmed,
                    stage="done",
                    text=tpl.balance_text(name, bal),
                    customer_id=pending["customer_id"],
                    balance=bal,
                )
            pending["stage"] = (
                "amount" if pending.get("amount_paise") is None else self._confirm_stage(pending)
            )
            return await self._respond_pending(event, pending, None, customers, None)

        if stage == "amount":
            amt = amount_paise if amount_paise is not None else parse_amount(transcript)
            if amt is None:
                if accept is False:
                    return await self._reject(event)
                return await self._respond_pending(event, pending, None, customers, None)
            pending["amount_paise"] = amt
            pending["stage"] = self._confirm_stage(pending)
            return await self._respond_pending(event, pending, None, customers, None)

        # confirm / confirm_large
        if accept is None and transcript is not None:
            yn = parse_rules(transcript).intent
            accept = True if yn == "confirm_yes" else False if yn == "confirm_no" else None
        if accept is None:
            return await self._finish(
                event,
                status=VoiceStatus.pending,
                stage=stage,
                text=tpl.SAY_YES_OR_NO,
                pending=pending,
            )
        if not accept:
            return await self._reject(event)
        if stage == "confirm_large":
            pending["large_ok"] = True
            pending["stage"] = "confirm"
            return await self._respond_pending(event, pending, None, customers, None)
        return await self._commit(shop_id, event, pending)

    def _choose_customer(
        self,
        pending: dict[str, Any],
        customers: list[CustomerRef],
        customer_id: int | None,
        transcript: str | None,
    ) -> dict[str, Any] | None:
        pool = [
            c for c in customers if not pending.get("candidates") or c.id in pending["candidates"]
        ]
        if customer_id is not None:
            hit = next((c for c in pool if c.id == customer_id), None)
            return {"customer_id": hit.id, "new_customer": None} if hit else None
        if not transcript:
            return None
        parsed = parse_rules(transcript)
        spoken = parsed.customer or transcript
        if pending.get("candidates"):
            best = max(pool, key=lambda c: max(score(spoken, n) for n in c.names), default=None)
            if best and max(score(spoken, n) for n in best.names) >= 70:
                return {"customer_id": best.id, "new_customer": None}
            return None
        res = resolve(spoken, customers)
        if res.kind == "matched" and res.customer:
            return {"customer_id": res.customer.id, "new_customer": None, "spoken_customer": spoken}
        if res.kind == "new" and parsed.intent not in ("confirm_no", "confirm_yes"):
            return {
                "customer_id": None,
                "new_customer": display_spoken(spoken),
                "spoken_customer": spoken,
            }
        return None

    async def _reject(self, event: VoiceEvent) -> TurnResult:
        return await self._finish(
            event, status=VoiceStatus.rejected, stage="done", text=tpl.CANCELLED
        )

    async def _commit(self, shop_id: int, event: VoiceEvent, pending: dict[str, Any]) -> TurnResult:
        intent = pending["intent"]
        try:
            if intent == "undo_last":
                reversal = svc.undo_last(self.db, shop_id=shop_id, voice_event_id=event.id)
                return await self._finish(
                    event,
                    status=VoiceStatus.confirmed,
                    stage="done",
                    text=tpl.UNDO_DONE,
                    entry_id=reversal.id,
                )
            customer_id = pending.get("customer_id")
            if customer_id is None and pending.get("new_customer"):
                customer_id = svc.create_customer(
                    self.db, shop_id=shop_id, display_name=pending["new_customer"]
                ).id
            elif customer_id is not None and pending.get("spoken_customer"):
                c = svc.get_customer(self.db, shop_id, customer_id)
                alias = new_alias(
                    pending["spoken_customer"], CustomerRef(c.id, c.display_name, tuple(c.aliases))
                )
                if alias:
                    svc.add_alias(self.db, c, alias)  # the system learns "Sharma uncle"
            lines = [
                svc.LineIn(i["name"], i.get("qty"), i.get("unit")) for i in pending.get("items", [])
            ]
            entry = svc.record_entry(
                self.db,
                shop_id=shop_id,
                type=EntryType(intent),
                amount_paise=pending["amount_paise"],
                customer_id=customer_id,
                voice_event_id=event.id,
                lines=lines,
            )
        except svc.LedgerError as e:
            self.db.rollback()
            event = self.db.get(VoiceEvent, event.id) or event
            event.error = f"ledger:{e.code}"
            return await self._finish(
                event, status=VoiceStatus.failed, stage="error", text=e.message
            )
        except IntegrityError:  # a concurrent "haan" already booked this event
            self.db.rollback()
            fresh = self.db.get(VoiceEvent, event.id)
            if fresh is not None and fresh.response_json and "event_id" in fresh.response_json:
                return TurnResult(**fresh.response_json)
            raise
        balance = (
            queries.customer_balance(self.db, shop_id, customer_id)
            if customer_id is not None
            else None
        )
        name = self._name_for({**pending, "customer_id": customer_id})
        return await self._finish(
            event,
            status=VoiceStatus.confirmed,
            stage="done",
            text=tpl.committed_text(intent, name, balance),
            entry_id=entry.id,
            customer_id=customer_id,
            balance=balance,
        )


def _options(candidates: list[Any]) -> list[dict[str, Any]]:
    return [{"customer_id": c.customer.id, "name": c.customer.display_name} for c in candidates]
