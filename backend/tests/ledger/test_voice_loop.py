"""Phase 4 acceptance: audio fixture -> Prisma(fake) -> NLU(rules) -> Timbre(fake) -> confirm ->
committed ledger entry -> spoken balance. Runs on SQLite and Postgres. No paid calls."""

from __future__ import annotations

import shutil
import subprocess
import uuid
from collections.abc import Callable, Iterator
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.api.voice import VoiceComponents, voice_components
from app.config import Settings, get_settings
from app.deps import current_shop_id, db_session
from app.ledger import queries as q
from app.ledger import service as svc
from app.ledger.models import LedgerEntry, Shop, VoiceEvent, VoiceStatus
from app.main import create_app
from app.nlu.parser import RulesParser
from app.voice.errors import GnaniError
from app.voice.fakes import FakeSTT, FakeTTS

FFMPEG = shutil.which("ffmpeg")
SHARMA_UDHAAR = "Sharma ji ne do kilo cheeni li, ek sau bees rupaye udhaar"


@pytest.fixture(scope="module")
def webm_clip(tmp_path_factory: pytest.TempPathFactory) -> bytes:
    """A real browser-style recording (opus/webm, 1.2 s of 'speech' with silence around it)."""
    if FFMPEG is None:
        pytest.skip("ffmpeg not installed")
    out = tmp_path_factory.mktemp("clips") / "sharma.webm"
    subprocess.run(  # noqa: S603
        [FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
         "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono:d=0.4",
         "-f", "lavfi", "-i", "sine=f=330:r=48000:d=1.2",
         "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono:d=0.4",
         "-filter_complex", "[0][1][2]concat=n=3:v=0:a=1", "-c:a", "libopus", str(out)],
        check=True,
    )  # fmt: skip
    return out.read_bytes()


class Harness:
    def __init__(self, client: TestClient, engine: Engine, shop: Shop, stt: FakeSTT,
                 tts: FakeTTS) -> None:  # fmt: skip
        self.client, self.engine, self.shop, self.stt, self.tts = client, engine, shop, stt, tts

    def db(self) -> Session:
        return Session(self.engine, expire_on_commit=False)

    def customer(self, name: str, *aliases: str) -> int:
        with self.db() as s:
            cid = svc.create_customer(s, shop_id=self.shop.id, display_name=name,
                                      aliases=aliases).id  # fmt: skip
            s.commit()
            return cid

    def say(self, transcript: str, key: str | None = None) -> dict[str, Any]:
        headers = {"Idempotency-Key": key} if key else {}
        r = self.client.post("/api/voice/turn", data={"transcript": transcript}, headers=headers)
        assert r.status_code == 200, r.text
        return dict(r.json())

    def confirm(self, event_id: int, **body: Any) -> dict[str, Any]:
        r = self.client.post(f"/api/voice/{event_id}/confirm", json=body)
        assert r.status_code == 200, r.text
        return dict(r.json())

    def entries(self) -> list[LedgerEntry]:
        with self.db() as s:
            return list(s.scalars(select(LedgerEntry).where(LedgerEntry.shop_id == self.shop.id)))

    def balance(self, cid: int) -> int:
        with self.db() as s:
            return q.customer_balance(s, self.shop.id, cid)


@pytest.fixture
def harness(engine: Engine, shop: Shop, tmp_path: Path) -> Iterator[Callable[..., Harness]]:
    clients: list[TestClient] = []

    def make(stt: FakeSTT | None = None, tts: FakeTTS | None = None,
             app_env: str = "test") -> Harness:  # fmt: skip
        stt = stt or FakeSTT(default=SHARMA_UDHAAR)
        tts = tts or FakeTTS()
        settings = Settings.model_validate({"app_env": app_env, "var_dir": tmp_path / "var",
                                            "nlu_mode": "rules", "gnani_api_key": ""})  # fmt: skip
        app = create_app()

        def _session() -> Iterator[Session]:
            s = Session(engine, expire_on_commit=False)
            try:
                yield s
            finally:
                s.close()

        app.dependency_overrides[db_session] = _session
        app.dependency_overrides[current_shop_id] = lambda: shop.id
        app.dependency_overrides[get_settings] = lambda: settings
        app.dependency_overrides[voice_components] = lambda: VoiceComponents(
            stt=stt, tts=tts, parser=RulesParser(), tts_voice_key="test"
        )
        client = TestClient(app)
        client.__enter__()
        clients.append(client)
        return Harness(client, engine, shop, stt, tts)

    yield make
    for c in clients:
        c.__exit__(None, None, None)


# ---------------------------------------------------------------- acceptance
def test_audio_to_committed_entry_to_spoken_balance(
    harness: Callable[..., Harness], webm_clip: bytes
) -> None:
    h = harness(stt=FakeSTT(script=[SHARMA_UDHAAR, "haan"]))
    cid = h.customer("Ramesh Sharma", "Sharma ji")

    r = h.client.post("/api/voice/turn", files={"audio": ("rec.webm", webm_clip, "audio/webm")},
                      headers={"Idempotency-Key": uuid.uuid4().hex})  # fmt: skip
    assert r.status_code == 200, r.text
    turn = r.json()
    assert turn["transcript"] == SHARMA_UDHAAR
    assert turn["intent"]["intent"] == "credit_sale"
    assert turn["intent"]["amount_paise"] == 12000
    assert turn["needs_confirmation"] is True
    assert turn["confirm_text"] == "Ramesh Sharma, ek sau bees rupaye udhaar. Sahi hai?"
    assert h.entries() == []  # NOTHING is written before "haan"
    audio = h.client.get(turn["confirm_audio_url"])
    assert audio.status_code == 200
    assert audio.headers["content-type"] == "audio/mpeg"
    assert audio.content == b"FAKEMP3:" + turn["confirm_text"].encode()

    # The shopkeeper says "haan" as an audio clip.
    r = h.client.post(f"/api/voice/{turn['event_id']}/confirm",
                      files={"audio": ("haan.webm", webm_clip, "audio/webm")})  # fmt: skip
    done = r.json()
    assert (done["status"], done["stage"], done["balance_paise"]) == ("confirmed", "done", 12000)
    assert done["confirm_text"] == "Likh diya. Ramesh Sharma ka total baaki ek sau bees rupaye."
    [entry] = h.entries()
    assert (entry.amount_paise, entry.customer_id, entry.voice_event_id) == (12000, cid,
                                                                             turn["event_id"])  # fmt: skip
    with h.db() as s:
        ev = s.get(VoiceEvent, turn["event_id"])
        assert ev is not None
        assert ev.status == VoiceStatus.confirmed
        assert ev.transcript == SHARMA_UDHAAR
        assert ev.nlu_source == "rules"
        assert ev.duration_ms
        assert ev.duration_ms >= 1200
        assert ev.latency_stt_ms is not None
        assert ev.latency_nlu_ms is not None
        assert ev.audio_path
        assert Path(ev.audio_path).exists()
        assert [ln.item_name for ln in s.get(LedgerEntry, entry.id).lines] == ["cheeni"]


def test_reject_writes_nothing(harness: Callable[..., Harness]) -> None:
    h = harness()
    h.customer("Ramesh Sharma", "Sharma ji")
    t = h.say(SHARMA_UDHAAR)
    r = h.confirm(t["event_id"], accept=False)
    assert (r["status"], r["confirm_text"]) == ("rejected", "Theek hai, cancel kar diya.")
    assert h.entries() == []


def test_double_tap_and_double_haan_book_once(harness: Callable[..., Harness]) -> None:
    h = harness()
    h.customer("Ramesh Sharma", "Sharma ji")
    key = uuid.uuid4().hex
    a, b = h.say(SHARMA_UDHAAR, key), h.say(SHARMA_UDHAAR, key)
    assert a["event_id"] == b["event_id"]
    first = h.confirm(a["event_id"], accept=True)
    second = h.confirm(a["event_id"], accept=True)
    assert first == second
    assert len(h.entries()) == 1


# ---------------------------------------------------------------- conversation branches
def test_two_sharmas_ask_then_tap(harness: Callable[..., Harness]) -> None:
    h = harness()
    h.customer("Ramesh Sharma", "Sharma ji")
    suresh = h.customer("Suresh Sharma")
    t = h.say(SHARMA_UDHAAR)
    assert t["stage"] == "disambiguate"
    assert t["confirm_text"] == "Kaun se Sharma ji: Ramesh ya Suresh?"
    assert {o["name"] for o in t["options"]} == {"Ramesh Sharma", "Suresh Sharma"}
    c = h.confirm(t["event_id"], customer_id=suresh)
    assert c["stage"] == "confirm"
    assert c["confirm_text"].startswith("Suresh Sharma, ek sau bees")
    done = h.confirm(t["event_id"], accept=True)
    assert done["customer_id"] == suresh
    assert h.balance(suresh) == 12000


def test_disambiguate_by_voice(harness: Callable[..., Harness]) -> None:
    h = harness()
    ramesh = h.customer("Ramesh Sharma", "Sharma ji")
    h.customer("Suresh Sharma")
    t = h.say(SHARMA_UDHAAR)
    r = h.client.post(f"/api/voice/{t['event_id']}/confirm", data={"transcript": "Ramesh"})
    assert r.json()["stage"] == "confirm"
    h.confirm(t["event_id"], accept=True)
    assert h.balance(ramesh) == 12000


def test_new_customer_created_on_haan(harness: Callable[..., Harness]) -> None:
    h = harness()
    t = h.say("Bunty ne 50 rupaye udhaar")
    assert t["confirm_text"] == "Naya customer Bunty. Bunty, pachaas rupaye udhaar. Sahi hai?"
    done = h.confirm(t["event_id"], accept=True)
    assert done["balance_paise"] == 5000
    with h.db() as s:
        assert [b.display_name for b in q.balances(s, h.shop.id)] == ["Bunty"]


def test_missing_amount_is_asked(harness: Callable[..., Harness]) -> None:
    h = harness()
    cid = h.customer("Ramesh Sharma", "Sharma ji")
    t = h.say("Sharma ji ne cheeni li")
    assert (t["stage"], t["confirm_text"]) == ("amount", "Ramesh Sharma ka kitne rupaye?")
    r = h.client.post(f"/api/voice/{t['event_id']}/confirm", data={"transcript": "dedh sau"})
    assert r.json()["confirm_text"] == "Ramesh Sharma, ek sau pachaas rupaye udhaar. Sahi hai?"
    h.confirm(t["event_id"], accept=True)
    assert h.balance(cid) == 15000


def test_missing_customer_is_asked(harness: Callable[..., Harness]) -> None:
    h = harness()
    gupta = h.customer("Anil Gupta", "Gupta ji")
    t = h.say("500 rupaye udhaar likho")
    assert (t["stage"], t["confirm_text"]) == ("customer", "Kis customer ka hai? Naam boliye.")
    r = h.client.post(f"/api/voice/{t['event_id']}/confirm", data={"transcript": "Gupta ji"})
    assert r.json()["stage"] == "confirm"
    h.confirm(t["event_id"], accept=True)
    assert h.balance(gupta) == 50000


def test_large_amount_needs_two_haans(harness: Callable[..., Harness]) -> None:
    h = harness()
    cid = h.customer("Ramesh Sharma", "Sharma ji")
    t = h.say("Sharma ji ne 60,000 rupaye udhaar")
    assert t["stage"] == "confirm_large"
    assert t["confirm_text"].endswith("Bada amount hai, pakka?")
    again = h.confirm(t["event_id"], accept=True)
    assert again["stage"] == "confirm"
    assert h.entries() == []
    h.confirm(t["event_id"], accept=True)
    assert h.balance(cid) == 6000000


def test_bare_haan_turn_confirms_latest_question(harness: Callable[..., Harness]) -> None:
    h = harness()
    cid = h.customer("Ramesh Sharma", "Sharma ji")
    h.say(SHARMA_UDHAAR)
    done = h.say("haan sahi hai")
    assert done["status"] == "confirmed"
    assert h.balance(cid) == 12000
    assert h.say("haan")["confirm_text"].startswith("Abhi koi entry haan ke liye baaki nahi")


def test_queries_answer_without_writing(harness: Callable[..., Harness]) -> None:
    h = harness()
    cid = h.customer("Ramesh Sharma", "Sharma ji")
    with h.db() as s:
        svc.record_entry(s, shop_id=h.shop.id, type=svc.EntryType.credit_sale, amount_paise=32000,
                         customer_id=cid)  # fmt: skip
        s.commit()
    b = h.say("Sharma ji ka hisaab batao")
    assert (b["stage"], b["confirm_text"]) == (
        "done",
        "Ramesh Sharma ka total baaki teen sau bees rupaye.",
    )
    assert h.say("kis kis ka baaki hai")["confirm_text"].startswith(
        "Sabse zyada baaki: Ramesh Sharma"
    )
    assert (
        h.say("aaj kitni bikri hui")["confirm_text"]
        == "Aaj ki bikri teen sau bees rupaye, 1 entry."
    )
    assert len(h.entries()) == 1


def test_undo_by_voice(harness: Callable[..., Harness]) -> None:
    h = harness()
    cid = h.customer("Ramesh Sharma", "Sharma ji")
    t = h.say(SHARMA_UDHAAR)
    h.confirm(t["event_id"], accept=True)
    u = h.say("pichhli entry cancel karo")
    assert (u["stage"], u["confirm_text"]) == (
        "confirm",
        "Pichhli entry cancel karoon? Haan ya nahi?",
    )
    done = h.confirm(u["event_id"], accept=True)
    assert done["confirm_text"] == "Pichhli entry cancel ho gayi."
    assert h.balance(cid) == 0
    assert len(h.entries()) == 2


def test_spoken_variant_is_learned_as_alias(harness: Callable[..., Harness]) -> None:
    h = harness()
    cid = h.customer("Ramesh Sharma")
    t = h.say("Sharma uncle ne 100 rupaye udhaar")
    h.confirm(t["event_id"], accept=True)
    with h.db() as s:
        assert "Sharma Uncle" in svc.get_customer(s, h.shop.id, cid).aliases


# ---------------------------------------------------------------- failures stay friendly
def test_empty_transcript(harness: Callable[..., Harness]) -> None:
    h = harness(stt=FakeSTT(default=""))
    r = h.client.post("/api/voice/turn", data={"transcript": ""})
    assert r.json()["confirm_text"] == "Awaaz saaf nahi aayi, dobara boliye."


def test_gnani_rate_limit_is_friendly_and_writes_nothing(
    harness: Callable[..., Harness], webm_clip: bytes
) -> None:
    h = harness(stt=FakeSTT(error=GnaniError("rate_limit")))
    r = h.client.post("/api/voice/turn", files={"audio": ("a.webm", webm_clip, "audio/webm")})
    body = r.json()
    assert (body["status"], body["confirm_text"]) == ("failed", "Ek second rukiye, phir boliye.")
    assert h.entries() == []


def test_accidental_tap_rejected_before_stt(
    harness: Callable[..., Harness], tmp_path: Path
) -> None:
    assert FFMPEG
    clip = tmp_path / "tap.webm"
    subprocess.run([FFMPEG, "-loglevel", "error", "-y", "-f", "lavfi", "-i",  # noqa: S603
                    "sine=f=440:r=48000:d=0.2", "-c:a", "libopus", str(clip)], check=True)  # fmt: skip
    stt = FakeSTT(default=SHARMA_UDHAAR)
    h = harness(stt=stt)
    r = h.client.post(
        "/api/voice/turn", files={"audio": ("t.webm", clip.read_bytes(), "audio/webm")}
    )
    assert r.json()["confirm_text"].startswith("Bahut chhota tha")
    assert stt.calls == []  # no credits spent


def test_tts_down_still_returns_text(harness: Callable[..., Harness]) -> None:
    h = harness(tts=FakeTTS(error=GnaniError("upstream")))
    h.customer("Ramesh Sharma", "Sharma ji")
    t = h.say(SHARMA_UDHAAR)
    assert t["confirm_audio_url"] is None
    assert t["needs_confirmation"]


def test_upload_limits_and_prod_guard(harness: Callable[..., Harness]) -> None:
    h = harness()
    assert h.client.post("/api/voice/turn", data={}).status_code == 400
    big = b"0" * (2 * 1024 * 1024 + 10)
    r = h.client.post("/api/voice/turn", files={"audio": ("x.webm", big, "audio/webm")})
    assert r.status_code == 413
    assert h.client.post("/api/voice/turn", data={"transcript": "x"},
                         headers={"Idempotency-Key": "bad key!"}).status_code == 400  # fmt: skip
    prod = harness(app_env="prod")
    assert prod.client.post("/api/voice/turn", data={"transcript": "haan"}).status_code == 400
    assert h.client.get("/api/voice/audio/../../etc/passwd.mp3").status_code == 404


def test_stale_question_expires(harness: Callable[..., Harness]) -> None:
    h = harness()
    h.customer("Ramesh Sharma", "Sharma ji")
    t = h.say(SHARMA_UDHAAR)
    with h.db() as s:
        ev = s.get(VoiceEvent, t["event_id"])
        assert ev is not None
        ev.created_at = ev.created_at - timedelta(minutes=11)
        s.commit()
    r = h.confirm(t["event_id"], accept=True)
    assert r["confirm_text"] == "Yeh entry purani ho gayi. Dobara boliye."
    assert h.entries() == []


def test_confirm_other_shops_event_is_404(harness: Callable[..., Harness]) -> None:
    h = harness()
    assert h.client.post("/api/voice/999999/confirm", json={"accept": True}).status_code == 404
