# Mail Ticker

A The Bat! Mail Tickeréhez hasonló értesítősáv Windowsra, Gmail-fiókhoz.
A képernyő tetején (vagy alján) futó sávon az olvasatlan levelek gördülnek
(feladó, tárgy, időpont). Kattintásra a levél megnyílik a böngészős Gmailben,
és lekerül a sávról.

## Telepítés

Töltsd le a legfrissebb **MailTicker-Setup-x.y.z.exe**-t:
<https://github.com/TebeeBoy/MailTicker/releases/latest>, és futtasd.

- Rendszergazdai jog nem kell: a program a saját felhasználód alá települ
  (`%LOCALAPPDATA%\Programs\MailTicker`).
- Start menü bejegyzés, választhatóan Asztal-ikon és indítás a Windows-zal.
- Eltávolítás: Beállítások → Alkalmazások (vagy Vezérlőpult → Programok és szolgáltatások)
  → Mail Ticker, illetve a Start menüből. A beállítások (`%APPDATA%\MailTicker`) megmaradnak.
- Ha korábban a hordozható `MailTicker.exe`-t használtad: lépj ki belőle, telepítsd ezt,
  majd a régi exe-t töröld. A beállításokat a telepített program is átveszi.

A hordozható `MailTicker.exe` (telepítés nélkül) továbbra is elérhető a kiadásoknál.

## Kezelés

| Művelet | Hatás |
|---|---|
| Kattintás egy levélre | megnyitja a Gmailben, lekerül a sávról, olvasott lesz |
| Egér a sáv fölött | a görgetés megáll |
| Kattintás a bal oldali számlálóra | Gmail beérkezett levelek |
| Húzás a számlálónál vagy a sáv üres részén | a sáv áthelyezése (a képernyő széleihez tapad) |
| Húzás a jobb szélső ⋮ fogantyúnál | szélesség állítása |
| Jobb klikk | Frissítés most · Beállítások · Alaphelyzet · Indítás a Windows-zal · Új verzió keresése · Kilépés |

A sáv helyét és szélességét a program megjegyzi. Ha a mentett hely már nem látszik
(pl. lecsatolt második monitor), a sáv visszaáll a bal felső sarokba.

A máshol (pl. telefonon) elolvasott levelek a következő lekérdezéskor maguktól eltűnnek.

### Levél megnyitása a már nyitott Gmailben

Ha van olyan böngészőablak (Chrome, Edge, Brave, Opera, Firefox), amelynek **aktív lapja**
ennek a fióknak a Gmailje, a program azt hozza előtérbe, és abban nyitja meg a levelet
(a címsorba illeszti a linket, a vágólap tartalmát utána visszaállítja). Ezután ellenőrzi,
hogy a Gmail tényleg átváltott-e (az ablak címe a levél tárgyára változik); ha 4 mp alatt
nem, vagy nincs ilyen ablak, vagy a Gmail-lap nem az aktív lap az ablakában, új lapon
nyitja meg – a levél így mindig megnyílik. Kikapcsolható a Beállításokban.

Ha a böngészőben több Google-fiókkal vagy bejelentkezve, a Beállításokban add meg, hányadik
fiók ez (a Gmail címében: `mail.google.com/mail/u/0/`, `/u/1/`…).

## Frissítés

A program indítás után és naponta egyszer megnézi a GitHubon, van-e új kiadás.
Ha van, a sávon zöld „⬆ Új verzió érhető el” elem jelenik meg; rákattintva frissít és
újraindul. Kézzel: jobb klikk → **Új verzió keresése…**.

A telepített program az új telepítőt tölti le és futtatja csendben (így a „Programok és
szolgáltatások” is a jó verziót mutatja); a hordozható exe saját magát cseréli ki.

Parancssorból vagy parancsikonról, kérdezés nélkül (ha a program épp nem fut):

```bat
MailTicker.exe --update
```

A hordozható exe-nek írható mappában kell lennie (pl. az Asztalon), a `Program Files`
alatt nem tudja kicserélni magát.

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

Az eredmény mindkét esetben a `dist/MailTicker.exe` (Python nélkül is fut) és a
`dist/MailTicker-Setup-<verzió>.exe` telepítő (`installer/MailTicker.iss`, Inno Setup 6).

**Windowson** (telepített Pythonnal; a telepítőhöz Inno Setup 6 is kell):

```bat
build.bat
```

**Linuxon** (Wine alatt, 32 bites Windows-os Pythonnal – az exe 64 bites Windowson is fut):

```bash
./build_wine.sh
```

Az első futás felépíti a build-környezetet a `~/.cache/mail_ticker_wine` mappába
(Python 3.11 + PyInstaller + Inno Setup), a további buildek ezt használják. Kell hozzá a `wine` (32 bites).

## Új verzió kiadása

A verziószám a `version.py`-ban van; ez kerül az exe tulajdonságaiba, a menübe és a
Beállítások ablak címébe.

1. `version.py`: `VERSION` átírása (pl. `0.4.0` → `0.4.1`), commit.
2. `./release.sh` – exe- és telepítő-build (Wine), commitolásuk a `releases/` mappába,
   tag, push, GitHub-kiadás mindkettővel.

Minden kiadott exe és telepítő megtalálható a tároló `releases/` mappájában is.

A telepített programok ezután maguktól jelzik az új verziót.

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
| `gmail_account_index` | 0 | hányadik bejelentkezett Google-fiók a böngészőben (`mail/u/<szám>/`) |
| `reuse_gmail_tab` | yes | a már megnyitott Gmail-ablakban nyissa meg a levelet |
| `update_check` | yes | új verzió keresése indításkor és naponta |
| `update_fg` | | az „új verzió” elem színe |

Napló: `%APPDATA%\MailTicker\mail_ticker.log`.
