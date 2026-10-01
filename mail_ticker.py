"""Mail Ticker – a The Bat! Mail Tickeréhez hasonló értesítősáv Gmailhez.

A képernyő tetején/alján futó sávon az olvasatlan levelek gördülnek.
Kattintásra a levél megnyílik a böngészős Gmailben és lekerül a sávról.

Indítás:  pythonw mail_ticker.py        (demó adatokkal: --demo)
"""
from __future__ import annotations

import logging
import logging.handlers
import os
import queue
import socket
import sys
import threading
import tkinter as tk
import tkinter.font as tkfont
import webbrowser
from datetime import datetime
from tkinter import messagebox, ttk
from urllib.parse import quote

import settings
import winutil
from gmail_client import AuthError, DemoClient, GmailClient, Message

GAP = 56  # képpont két levél között
TICK_MS = 20  # gördítés képkockaideje
MIN_POLL_SECONDS = 15
MIN_WIDTH = 220  # a sáv legkisebb szélessége
SNAP = 12  # ennyi képponton belül a képernyő széléhez tapad
DRAG_THRESHOLD = 4  # ennél kisebb elmozdulás még kattintásnak számít

log = logging.getLogger("mail_ticker")


def make_text_filter(root: tk.Tk):
    """A régi Tk (8.6.10 előtt) és az X11-es Tk elhasal a BMP-n kívüli karaktereken (pl. emojik)."""
    patch = tuple(int(p) for p in root.tk.call("info", "patchlevel").split(".")[:3])
    if winutil.IS_WINDOWS and patch >= (8, 6, 10):
        return lambda text: text
    return lambda text: "".join(ch if ord(ch) <= 0xFFFF else "\ufffd" for ch in text)


def format_date(date: datetime | None) -> str:
    if date is None:
        return ""
    now = datetime.now(date.tzinfo)
    if date.date() == now.date():
        return date.strftime("%H:%M")
    return date.strftime("%m.%d. %H:%M")


class TickerApp:
    def __init__(self, root: tk.Tk, cfg: settings.Settings, demo: bool = False):
        self.root = root
        self.cfg = cfg
        self.demo = demo
        self.client = None
        self.queue: queue.Queue = queue.Queue()
        self.wake = threading.Event()
        self.order: list[int] = []  # uid-k a sávon, balról jobbra
        self.messages: dict[int, Message] = {}
        self.dismissed: set[int] = set()  # rákattintott, de a szerver még olvasatlannak mutathatja
        self.loaded = False
        self.paused = False
        self.error: str | None = None
        self._drag: dict | None = None

        self._build_ui()
        self.apply_settings()
        threading.Thread(target=self._poll_loop, daemon=True).start()
        self.root.after(TICK_MS, self._tick)
        self.root.after(200, self._process_queue)
        if not demo and not (cfg["email"] and cfg.password):
            self.root.after(300, self.open_settings)

    # ---------- felület ----------

    def _build_ui(self) -> None:
        cfg = self.cfg
        self.root.title("Mail Ticker")
        self.root.overrideredirect(True)  # keret és tálcagomb nélkül
        self.root.attributes("-topmost", True)

        family, size = cfg["font_family"], cfg.get_int("font_size")
        self.font = tkfont.Font(self.root, family=family, size=size)
        self.bold = tkfont.Font(self.root, family=family, size=size, weight="bold")
        self.small = tkfont.Font(self.root, family=family, size=max(size - 1, 7))
        self.safe_text = make_text_filter(self.root)
        self.bar_h = self.bold.metrics("linespace") + 10
        self.mid_y = self.bar_h // 2

        self.badge = tk.Label(
            self.root, text="✉ …", font=self.bold, fg="white", bg=cfg["badge_bg"], padx=10, cursor="fleur"
        )
        self.badge.pack(side="left", fill="y")
        self.grip = tk.Label(
            self.root, text="⋮", font=self.bold, fg="white", bg=cfg["badge_bg"], padx=3, cursor="sb_h_double_arrow"
        )
        self.grip.pack(side="right", fill="y")
        self.canvas = tk.Canvas(self.root, bg=cfg["bg"], height=self.bar_h, highlightthickness=0, bd=0)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.status_id = self.canvas.create_text(
            12, self.mid_y, anchor="w", font=self.font, fill=cfg["date_fg"], text="Kapcsolódás…"
        )

        self.autostart_var = tk.BooleanVar(value=winutil.autostart_enabled())
        self.menu = tk.Menu(self.root, tearoff=False)
        self.menu.add_command(label="Gmail megnyitása", command=self.open_inbox)
        self.menu.add_command(label="Frissítés most", command=self.wake.set)
        self.menu.add_command(label="Beállítások…", command=self.open_settings)
        self.menu.add_command(label="Alaphelyzet (teljes szélesség, fent)", command=self.reset_geometry)
        if winutil.IS_WINDOWS:
            self.menu.add_checkbutton(
                label="Indítás a Windows-zal", variable=self.autostart_var, command=self._toggle_autostart
            )
        self.menu.add_separator()
        self.menu.add_command(label="Kilépés", command=self.root.destroy)

        for widget in (self.badge, self.canvas, self.grip):
            widget.bind("<Button-3>", self._show_menu)
            widget.bind("<B1-Motion>", self._on_drag)
            widget.bind("<ButtonRelease-1>", self._end_drag)
        self.badge.bind("<ButtonPress-1>", lambda e: self._start_drag(e, "move", on_click=self.open_inbox))
        self.canvas.bind("<ButtonPress-1>", self._canvas_press)
        self.grip.bind("<ButtonPress-1>", lambda e: self._start_drag(e, "resize"))
        self.canvas.bind("<Enter>", lambda e: setattr(self, "paused", True))
        self.canvas.bind("<Leave>", lambda e: setattr(self, "paused", False))

    def apply_settings(self) -> None:
        cfg = self.cfg
        self.root.attributes("-alpha", min(max(cfg.get_float("alpha"), 0.3), 1.0))
        self._place_window()

        if self.demo:
            new_client = self.client or DemoClient()
        elif cfg["email"] and cfg.password:
            new_client = GmailClient(cfg["email"], cfg.password)
        else:
            new_client = None
        if getattr(self.client, "address", None) != getattr(new_client, "address", None):
            self._clear()
        self.client = new_client
        self.wake.set()

    # ---------- elhelyezés: mozgatás és átméretezés ----------

    def _place_window(self) -> None:
        cfg = self.cfg
        left, top, right, bottom = winutil.work_area(self.root)
        width = cfg.get_int("width") or (right - left)
        width = max(MIN_WIDTH, width)
        x, y = cfg.get_optional_int("x"), cfg.get_optional_int("y")
        if x is None or y is None or not winutil.is_visible(x, y, width, self.bar_h, self.root):
            x, y = left, top
        self.root.geometry(f"{width}x{self.bar_h}+{x}+{y}")

    def reset_geometry(self) -> None:
        for key in ("x", "y"):
            self.cfg.set(key, "")
        self.cfg.set("width", 0)
        settings.save(self.cfg)
        self._place_window()

    def _canvas_press(self, event) -> None:
        if "msg" in self.canvas.gettags("current"):
            return  # levélre kattintott – azt a levél saját eseménye kezeli
        self._start_drag(event, "move")

    def _start_drag(self, event, mode: str, on_click=None) -> None:
        self._drag = {
            "mode": mode,
            "x": event.x_root,
            "y": event.y_root,
            "win_x": self.root.winfo_x(),
            "win_y": self.root.winfo_y(),
            "width": self.root.winfo_width(),
            "moved": False,
            "on_click": on_click,
            "result": None,  # (szélesség, x, y) – a winfo_* csak késve frissül, ezért ezt mentjük
        }

    def _on_drag(self, event) -> None:
        d = self._drag
        if d is None:
            return
        dx, dy = event.x_root - d["x"], event.y_root - d["y"]
        if not d["moved"] and abs(dx) + abs(dy) < DRAG_THRESHOLD:
            return
        d["moved"] = True
        if d["mode"] == "move":
            x, y = self._snap(d["win_x"] + dx, d["win_y"] + dy, d["width"])
            self.root.geometry(f"+{x}+{y}")
            d["result"] = (d["width"], x, y)
        else:
            width = max(MIN_WIDTH, d["width"] + dx)
            left, top, right, bottom = winutil.work_area(self.root)
            if abs(d["win_x"] + width - right) < SNAP:
                width = right - d["win_x"]
            self.root.geometry(f"{width}x{self.bar_h}")
            d["result"] = (width, d["win_x"], d["win_y"])

    def _end_drag(self, event) -> None:
        d, self._drag = self._drag, None
        if d is None:
            return
        if d["result"]:
            width, x, y = d["result"]
            self.cfg.set("x", x)
            self.cfg.set("y", y)
            self.cfg.set("width", width)
            settings.save(self.cfg)
        elif not d["moved"] and d["on_click"]:
            d["on_click"]()

    def _snap(self, x: int, y: int, width: int) -> tuple[int, int]:
        """A munkaterület (tálca nélküli képernyő) széleihez tapasztja a sávot."""
        left, top, right, bottom = winutil.work_area(self.root)
        if abs(x - left) < SNAP:
            x = left
        elif abs(x + width - right) < SNAP:
            x = right - width
        if abs(y - top) < SNAP:
            y = top
        elif abs(y + self.bar_h - bottom) < SNAP:
            y = bottom - self.bar_h
        return x, y

    def _show_menu(self, event) -> None:
        self.autostart_var.set(winutil.autostart_enabled())
        self.menu.tk_popup(event.x_root, event.y_root)

    def _toggle_autostart(self) -> None:
        try:
            winutil.set_autostart(self.autostart_var.get())
        except OSError as e:
            messagebox.showerror("Mail Ticker", f"Nem sikerült módosítani az automatikus indítást:\n{e}")

    def open_settings(self) -> None:
        SettingsDialog(self)

    # ---------- levelek a sávon ----------

    def _tail_x(self) -> float:
        """Ahová a következő levél kerül: az utolsó után, de legalább a sáv jobb széléhez."""
        width = self.canvas.winfo_width()
        if self.order:
            bbox = self.canvas.bbox(f"m{self.order[-1]}")
            if bbox:
                return max(bbox[2] + GAP, width)
        return width

    def _add_item(self, msg: Message) -> None:
        cfg = self.cfg
        tag = f"m{msg.uid}"
        x = self._tail_x()
        rect = self.canvas.create_rectangle(x, 0, x, self.bar_h, fill=cfg["bg"], outline="", tags=("msg", tag))
        cx = x + 8
        parts = [
            ("✉", self.font, cfg["sender_fg"]),
            (self.safe_text(msg.sender), self.bold, cfg["sender_fg"]),
            (self.safe_text(msg.subject), self.font, cfg["subject_fg"]),
            (format_date(msg.date), self.small, cfg["date_fg"]),
        ]
        for text, font, color in parts:
            if not text:
                continue
            item = self.canvas.create_text(
                cx, self.mid_y, text=text, anchor="w", font=font, fill=color, tags=("msg", tag)
            )
            cx = self.canvas.bbox(item)[2] + 8
        self.canvas.coords(rect, x, 0, cx, self.bar_h)

        self.canvas.tag_bind(tag, "<Button-1>", lambda e, uid=msg.uid: self.open_message(uid))
        self.canvas.tag_bind(tag, "<Enter>", lambda e, r=rect: self._hover(r, True))
        self.canvas.tag_bind(tag, "<Leave>", lambda e, r=rect: self._hover(r, False))
        self.order.append(msg.uid)
        self.messages[msg.uid] = msg

    def _hover(self, rect: int, on: bool) -> None:
        self.canvas.itemconfigure(rect, fill=self.cfg["hover_bg" if on else "bg"])
        self.canvas.configure(cursor="hand2" if on else "")

    def _remove_item(self, uid: int) -> None:
        self.canvas.delete(f"m{uid}")
        self.canvas.configure(cursor="")
        if uid in self.order:
            self.order.remove(uid)
        self.messages.pop(uid, None)

    def _clear(self) -> None:
        for uid in list(self.order):
            self._remove_item(uid)
        self.dismissed.clear()
        self.loaded = False

    def _sync(self, unread: list[Message]) -> None:
        unread_uids = {m.uid for m in unread}
        self.dismissed &= unread_uids
        for uid in list(self.order):
            if uid not in unread_uids:  # máshol (pl. telefonon) már elolvasták
                self._remove_item(uid)
        new = [m for m in unread if m.uid not in self.messages and m.uid not in self.dismissed]
        if not self.loaded:
            new.reverse()  # induláskor a legfrissebb jön először
            self.loaded = True
        for msg in new:
            self._add_item(msg)
        if new:
            log.info("%d új olvasatlan levél", len(new))

    def _tick(self) -> None:
        if self.order and not self.paused:
            self.canvas.move("msg", -self.cfg.get_float("speed"), 0)
            first = self.order[0]
            bbox = self.canvas.bbox(f"m{first}")
            width = self.canvas.winfo_width()
            if bbox and bbox[0] > width:  # pl. keskenyítés után: ne kelljen kivárni, míg beér
                self.canvas.move("msg", width - bbox[0], 0)
            elif bbox and bbox[2] < 0:  # balra kifutott → a sor végére kerül
                self.order.pop(0)
                self.canvas.move(f"m{first}", self._tail_x() - bbox[0], 0)
                self.order.append(first)
        self.root.after(TICK_MS, self._tick)

    def _refresh_status(self) -> None:
        cfg = self.cfg
        count = len(self.order)
        self.badge.configure(text=f"✉ {count}" if not self.error else "⚠", bg=cfg["error_bg" if self.error else "badge_bg"])
        if count:
            self.canvas.itemconfigure(self.status_id, state="hidden")
        else:
            text = self.error or "Nincs olvasatlan levél"
            self.canvas.itemconfigure(self.status_id, state="normal", text=text)

        if cfg.get_bool("hide_when_empty") and not count and not self.error:
            self.root.withdraw()
        elif self.root.state() == "withdrawn":
            self.root.deiconify()
            self.root.attributes("-topmost", True)

    # ---------- műveletek ----------

    def _gmail_base(self) -> str:
        address = getattr(self.client, "address", "") or "0"
        return f"https://mail.google.com/mail/u/{quote(address)}/"

    def open_inbox(self) -> None:
        webbrowser.open(self._gmail_base() + "#inbox")

    def open_message(self, uid: int) -> None:
        msg = self.messages.get(uid)
        if msg is None:
            return
        webbrowser.open(f"{self._gmail_base()}#all/{msg.gm_msgid:x}")
        self.dismissed.add(uid)
        self._remove_item(uid)
        self._refresh_status()
        if self.cfg.get_bool("mark_as_read"):
            threading.Thread(target=self._mark_seen, args=(self.client, uid), daemon=True).start()

    # ---------- háttérszálak ----------

    def _mark_seen(self, client, uid: int) -> None:
        try:
            client.mark_seen(uid)
        except Exception:
            log.exception("Nem sikerült olvasottnak jelölni (uid=%s)", uid)

    def _poll_loop(self) -> None:
        while True:
            self.wake.clear()
            client = self.client
            if client is None:
                self.queue.put(("error", None, "Nincs beállítva Gmail-fiók – jobb klikk → Beállítások"))
            else:
                try:
                    self.queue.put(("messages", client, client.fetch_unread()))
                except AuthError as e:
                    log.warning("Bejelentkezési hiba: %s", e)
                    self.queue.put(("error", client, "Sikertelen bejelentkezés – ellenőrizd a címet és az alkalmazásjelszót"))
                except Exception as e:
                    log.exception("Lekérdezési hiba")
                    self.queue.put(("error", client, f"Kapcsolódási hiba: {e}"))
            self.wake.wait(max(self.cfg.get_int("poll_seconds"), MIN_POLL_SECONDS))

    def _process_queue(self) -> None:
        try:
            while True:
                kind, client, payload = self.queue.get_nowait()
                if client is not self.client:
                    continue  # időközben fiókot váltottak
                if kind == "messages":
                    self.error = None
                    self._sync(payload)
                else:
                    self.error = payload
                self._refresh_status()
        except queue.Empty:
            pass
        self.root.after(200, self._process_queue)


class SettingsDialog(tk.Toplevel):
    def __init__(self, app: TickerApp):
        super().__init__(app.root)
        self.app = app
        cfg = app.cfg
        self.title("Mail Ticker – Beállítások")
        self.resizable(False, False)
        self.attributes("-topmost", True)

        self.email = tk.StringVar(value=cfg["email"])
        self.password = tk.StringVar(value=cfg.password)
        self.poll = tk.StringVar(value=cfg["poll_seconds"])
        self.speed = tk.StringVar(value=cfg["speed"])
        self.width = tk.StringVar(value=str(app.root.winfo_width()))
        self.hide_empty = tk.BooleanVar(value=cfg.get_bool("hide_when_empty"))
        self.mark_read = tk.BooleanVar(value=cfg.get_bool("mark_as_read"))

        frame = ttk.Frame(self, padding=14)
        frame.pack(fill="both", expand=True)
        rows = [
            ("Gmail-cím:", ttk.Entry(frame, textvariable=self.email, width=34)),
            ("Alkalmazásjelszó:", ttk.Entry(frame, textvariable=self.password, width=34, show="•")),
            ("Lekérdezés (mp):", ttk.Spinbox(frame, textvariable=self.poll, from_=MIN_POLL_SECONDS, to=3600, width=8)),
            ("Gördülési sebesség:", ttk.Spinbox(frame, textvariable=self.speed, from_=0.5, to=10, increment=0.5, width=8)),
        ]
        for i, (label, widget) in enumerate(rows):
            ttk.Label(frame, text=label).grid(row=i, column=0, sticky="w", pady=3)
            widget.grid(row=i, column=1, sticky="w", pady=3)

        ttk.Label(frame, text="Szélesség (px):").grid(row=4, column=0, sticky="w", pady=3)
        ttk.Spinbox(frame, textvariable=self.width, from_=MIN_WIDTH, to=10000, increment=50, width=8).grid(
            row=4, column=1, sticky="w", pady=3
        )

        ttk.Checkbutton(frame, text="Kattintáskor olvasottnak jelölés a Gmailben", variable=self.mark_read).grid(
            row=5, column=0, columnspan=2, sticky="w", pady=(8, 2)
        )
        ttk.Checkbutton(frame, text="Sáv elrejtése, ha nincs olvasatlan levél", variable=self.hide_empty).grid(
            row=6, column=0, columnspan=2, sticky="w"
        )
        ttk.Label(
            frame,
            foreground="#555",
            wraplength=360,
            justify="left",
            text="Gmail-alkalmazásjelszó kell (nem a normál jelszó): Google-fiók → Biztonság → "
            "Kétlépcsős azonosítás bekapcsolása, majd myaccount.google.com/apppasswords.",
        ).grid(row=7, column=0, columnspan=2, sticky="w", pady=(10, 0))

        buttons = ttk.Frame(frame)
        buttons.grid(row=8, column=0, columnspan=2, sticky="e", pady=(14, 0))
        ttk.Button(buttons, text="Mégse", command=self.destroy).pack(side="right")
        ttk.Button(buttons, text="Mentés", command=self._save).pack(side="right", padx=6)

        self.bind("<Return>", lambda e: self._save())
        self.bind("<Escape>", lambda e: self.destroy())
        self.update_idletasks()
        x = (self.winfo_screenwidth() - self.winfo_reqwidth()) // 2
        y = (self.winfo_screenheight() - self.winfo_reqheight()) // 3
        self.geometry(f"+{x}+{y}")
        self.focus_force()
        rows[0][1].focus_set()

    def _save(self) -> None:
        try:
            poll = int(self.poll.get())
            speed = float(self.speed.get().replace(",", "."))
            width = int(self.width.get())
            if poll < MIN_POLL_SECONDS or speed <= 0 or width < MIN_WIDTH:
                raise ValueError
        except ValueError:
            messagebox.showerror(
                "Mail Ticker", f"A lekérdezés legalább {MIN_POLL_SECONDS} mp, a szélesség legalább {MIN_WIDTH} px, "
                "a sebesség pozitív szám legyen.", parent=self
            )
            return
        cfg = self.app.cfg
        cfg.set("email", self.email.get().strip())
        cfg.password = self.password.get().strip()
        cfg.set("poll_seconds", poll)
        cfg.set("speed", speed)
        cfg.set("width", width)
        if cfg.get_optional_int("x") is None:  # eddig alaphelyzetben volt: rögzítjük a mostani helyét
            cfg.set("x", self.app.root.winfo_x())
            cfg.set("y", self.app.root.winfo_y())
        cfg.set("hide_when_empty", "yes" if self.hide_empty.get() else "no")
        cfg.set("mark_as_read", "yes" if self.mark_read.get() else "no")
        settings.save(cfg)
        self.destroy()
        self.app.apply_settings()


def setup_logging() -> None:
    os.makedirs(settings.APP_DIR, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        os.path.join(settings.APP_DIR, "mail_ticker.log"), maxBytes=1_000_000, backupCount=1, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler])


def main() -> None:
    setup_logging()
    if not winutil.acquire_single_instance():
        return
    winutil.enable_dpi_awareness()
    socket.setdefaulttimeout(30)  # ne akadjon el a lekérdezés hálózati hibánál
    root = tk.Tk()
    TickerApp(root, settings.load(), demo="--demo" in sys.argv)
    root.mainloop()


if __name__ == "__main__":
    main()
