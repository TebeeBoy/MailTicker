#!/usr/bin/env bash
# Új verzió kiadása GitHub Releases-be; a telepített programok innen frissítik magukat.
#
# Lépések előtte: version.py-ban a VERSION átírása, majd commit.
# A szkript: exe + telepítő build (Wine) → releases/ commit → git tag (vX.Y.Z)
# → push → GitHub release (MailTicker.exe + MailTicker-Setup-X.Y.Z.exe).
# A kiadási jegyzet a legutóbbi tag óta készült commitok címeiből áll.
set -euo pipefail
cd "$(dirname "$0")"

GH="${GH:-$(command -v gh || echo "$HOME/.local/bin/gh")}"
VERSION="$(python3 -c 'from version import VERSION; print(VERSION)')"
TAG="v$VERSION"

if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "Vannak nem commitolt változások – előbb commitold őket." >&2
    exit 1
fi
if "$GH" release view "$TAG" >/dev/null 2>&1; then
    echo "A $TAG kiadás már létezik – írd át a VERSION-t a version.py-ban." >&2
    exit 1
fi

if git rev-parse -q --verify "refs/tags/$TAG" >/dev/null; then
    echo "A $TAG tag már létezik – írd át a VERSION-t a version.py-ban." >&2
    exit 1
fi
PREV_TAG="$(git describe --tags --abbrev=0 2>/dev/null || true)"

./build_wine.sh
strings -el dist/MailTicker.exe | grep -qx "$VERSION" || {
    echo "Az exe-ben nem $VERSION a verzió – a build hibás." >&2
    exit 1
}

SETUP="dist/MailTicker-Setup-$VERSION.exe"
test -f "$SETUP" || { echo "Nem készült el a telepítő: $SETUP" >&2; exit 1; }

# az exe és a telepítő is verziózva kerül a gitbe (releases/); a tag erre a commitra mutat
mkdir -p releases
cp dist/MailTicker.exe "releases/MailTicker-$VERSION.exe"
cp "$SETUP" releases/
git add "releases/MailTicker-$VERSION.exe" "releases/MailTicker-Setup-$VERSION.exe"
git commit -q -m "Kiadás $VERSION: MailTicker.exe és telepítő"
git tag -a "$TAG" -m "Mail Ticker $VERSION"

NOTES="$(git log --no-merges --format='- %s' ${PREV_TAG:+"$PREV_TAG"..}"$TAG" | grep -v '^- Kiadás [0-9.]*: MailTicker.exe' || true)"
git push origin HEAD
git push origin "$TAG"
"$GH" release create "$TAG" "$SETUP" dist/MailTicker.exe --title "Mail Ticker $VERSION" --notes "$NOTES"
echo ">> Kiadva: $TAG"
