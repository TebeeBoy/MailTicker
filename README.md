# Mail Ticker

A The Bat! Mail Tickeréhez hasonló értesítősáv Windowsra, Gmail-fiókhoz.
A képernyő tetején (vagy alján) futó sávon az olvasatlan levelek gördülnek
(feladó, tárgy, időpont). Kattintásra a levél megnyílik a böngészős Gmailben,
és lekerül a sávról.

## Kezelés

| Művelet | Hatás |
|---|---|
| Kattintás egy levélre | megnyitja a Gmailben, lekerül a sávról, olvasott lesz |
| Egér a sáv fölött | a görgetés megáll |
| Kattintás a bal oldali számlálóra | Gmail beérkezett levelek |
| Húzás a számlálónál vagy a sáv üres részén | a sáv áthelyezése (a képernyő széleihez tapad) |
| Húzás a jobb szélső ⋮ fogantyúnál | szélesség állítása |
| Jobb klikk | Frissítés most · Beállítások · Alaphelyzet · Indítás a Windows-zal · Kilépés |

A sáv helyét és szélességét a program megjegyzi. Ha a mentett hely már nem látszik
(pl. lecsatolt második monitor), a sáv visszaáll a bal felső sarokba.

A máshol (pl. telefonon) elolvasott levelek a következő lekérdezéskor maguktól eltűnnek.

## Gmail előkészítése

A program IMAP-on éri el a fiókot, ehhez **alkalmazásjelszó** kell (a normál jelszó nem működik):

1. Google-fiók → Biztonság → **Kétlépcsős azonosítás** bekapcsolása.
2. <https://myaccount.google.com/apppasswords> → új alkalmazásjelszó (pl. „Mail Ticker”).
3. Az első indításkor felugró Beállítások ablakba a Gmail-cím és ez a 16 karakteres jelszó kerül.

A jelszót a program Windows DPAPI-val titkosítva tárolja (csak a saját Windows-felhasználód tudja visszafejteni).

## Futtatás

Python 3.9+ kell, külső csomag nem.

```bat
pythonw mail_ticker.py          :: normál indítás
python  mail_ticker.py --demo   :: kipróbálás kitalált levelekkel, Gmail nélkül
```

## Exe készítése

```bat
build.bat
```

Az eredmény a `dist\MailTicker.exe`, ami Python nélkül is fut.

## Beállítások

`%APPDATA%\MailTicker\config.ini` – a fontosabbak a Beállítások ablakban is állíthatók.
A kinézet (színek, betűtípus, átlátszóság) a fájlban módosítható, utána újra kell indítani a programot:

| Kulcs | Alapérték | Jelentés |
|---|---|---|
| `poll_seconds` | 60 | lekérdezés gyakorisága (mp, min. 15) |
| `x`, `y`, `width` | (üres), 0 | a sáv helye és szélessége (húzással állítódik; 0 = teljes szélesség) |
| `speed` | 1.5 | gördülési sebesség |
| `font_family`, `font_size` | Segoe UI, 10 | betűtípus |
| `bg`, `hover_bg`, `badge_bg`, `error_bg` | | háttérszínek |
| `sender_fg`, `subject_fg`, `date_fg` | | szövegszínek |
| `alpha` | 0.95 | átlátszóság (0.3–1.0) |
| `hide_when_empty` | no | sáv elrejtése, ha nincs olvasatlan levél |
| `mark_as_read` | yes | kattintáskor olvasottnak jelölés a Gmailben |

Napló: `%APPDATA%\MailTicker\mail_ticker.log`.
