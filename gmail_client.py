"""Gmail olvasatlan leveleinek lekérdezése IMAP-on keresztül."""
from __future__ import annotations

import email
import email.policy
import imaplib
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from email.header import decode_header, make_header
from email.utils import parseaddr, parsedate_to_datetime
from typing import Optional

IMAP_HOST = "imap.gmail.com"
FETCH_LIMIT = 50  # ennél több olvasatlan levélből csak a legújabbakat mutatjuk

_UID_RE = re.compile(rb"UID (\d+)")
_MSGID_RE = re.compile(rb"X-GM-MSGID (\d+)")


class AuthError(Exception):
    pass


@dataclass
class Message:
    uid: int
    gm_msgid: int  # Gmail saját azonosítója, ebből lesz a böngészős link
    sender: str
    subject: str
    date: Optional[datetime]


def _decode(value: Optional[str]) -> str:
    if not value:
        return ""
    try:
        text = str(make_header(decode_header(value)))
    except Exception:
        text = value
    return " ".join(text.split())


def _header(msg, name: str):
    """A modern policy jól kezeli a vegyes/8 bites fejléceket, de hibás fejlécnél kivételt dobhat."""
    try:
        return msg[name]
    except Exception:
        return None


def _parse_headers(uid: int, gm_msgid: int, raw: bytes) -> Message:
    msg = email.message_from_bytes(raw, policy=email.policy.default)
    legacy = email.message_from_bytes(raw)

    sender = ""
    from_ = _header(msg, "From")
    try:
        if from_ is not None and from_.addresses:
            sender = from_.addresses[0].display_name or from_.addresses[0].addr_spec
    except Exception:
        pass
    if not sender:
        name, addr = parseaddr(legacy.get("From", ""))
        sender = _decode(name) or addr or "(ismeretlen feladó)"
    sender = " ".join(sender.split())

    subject = _header(msg, "Subject")
    subject = " ".join(str(subject).split()) if subject is not None else _decode(legacy.get("Subject"))

    date = getattr(_header(msg, "Date"), "datetime", None)
    if date is None:
        try:
            date = parsedate_to_datetime(legacy.get("Date"))
        except Exception:
            date = None
    if date is not None and date.tzinfo:
        date = date.astimezone()
    return Message(uid, gm_msgid, sender, subject or "(nincs tárgy)", date)


def _check(typ: str, data) -> None:
    if typ != "OK":
        raise imaplib.IMAP4.error(f"IMAP hiba: {data!r}")


class GmailClient:
    def __init__(self, address: str, password: str):
        self.address = address
        self.password = password.replace(" ", "")  # az alkalmazásjelszót szóközökkel mutatja a Google

    def _connect(self) -> imaplib.IMAP4_SSL:
        conn = imaplib.IMAP4_SSL(IMAP_HOST)
        try:
            conn.login(self.address, self.password)
        except imaplib.IMAP4.error as e:
            _logout(conn)
            raise AuthError(str(e)) from e
        return conn

    def fetch_unread(self) -> list[Message]:
        conn = self._connect()
        try:
            _check(*conn.select("INBOX", readonly=True))
            typ, data = conn.uid("SEARCH", None, "UNSEEN")
            _check(typ, data)
            uids = data[0].split()[-FETCH_LIMIT:]
            if not uids:
                return []
            typ, data = conn.uid(
                "FETCH",
                b",".join(uids).decode("ascii"),
                "(X-GM-MSGID BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])",
            )
            _check(typ, data)
            messages = []
            for part in data:
                if not isinstance(part, tuple):
                    continue
                meta, raw = part
                uid_m, msgid_m = _UID_RE.search(meta), _MSGID_RE.search(meta)
                if uid_m and msgid_m:
                    messages.append(_parse_headers(int(uid_m.group(1)), int(msgid_m.group(1)), raw))
            messages.sort(key=lambda m: m.uid)
            return messages
        finally:
            _logout(conn)

    def mark_seen(self, uid: int) -> None:
        conn = self._connect()
        try:
            _check(*conn.select("INBOX"))
            _check(*conn.uid("STORE", str(uid), "+FLAGS", "(\\Seen)"))
        finally:
            _logout(conn)


class DemoClient:
    """Kitalált levelek a kinézet kipróbálásához (--demo kapcsoló)."""

    address = "demo@gmail.com"

    def __init__(self):
        now = datetime.now()
        samples = [
            ("Kovács Anna", "Holnapi megbeszélés – módosult az időpont"),
            ("GitHub", "[mail_ticker] New issue: ticker speed setting"),
            ("Nagy Péter", "Re: Számla 2026/0915"),
            ("Google", "Biztonsági figyelmeztetés: új bejelentkezés Windows rendszeren"),
            ("Szabó Éva", "Fotók a hétvégéről 📷"),
        ]
        self._unread = [
            Message(i + 1, 0x18F00000000 + i, s, subj, now - timedelta(minutes=17 * (len(samples) - i)))
            for i, (s, subj) in enumerate(samples)
        ]

    def fetch_unread(self) -> list[Message]:
        return list(self._unread)

    def mark_seen(self, uid: int) -> None:
        self._unread = [m for m in self._unread if m.uid != uid]


def _logout(conn: imaplib.IMAP4) -> None:
    try:
        conn.logout()
    except Exception:
        pass
