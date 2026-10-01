#!/usr/bin/env bash
# Új verzió kiadása GitHub Releases-be; a telepített programok innen frissítik magukat.
#
# Lépések előtte: version.py-ban a VERSION átírása, majd commit.
# A szkript: git tag (vX.Y.Z) → exe build (Wine) → push → GitHub release + MailTicker.exe.
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

PREV_TAG="$(git describe --tags --abbrev=0 HEAD^ 2>/dev/null || true)"
if git rev-parse -q --verify "refs/tags/$TAG" >/dev/null; then
    [ "$(git rev-list -n1 "$TAG")" = "$(git rev-parse HEAD)" ] || {
        echo "A $TAG tag nem a mostani commitra mutat." >&2
        exit 1
    }
else
    git tag -a "$TAG" -m "Mail Ticker $VERSION"
fi

./build_wine.sh
strings -el dist/MailTicker.exe | grep -qx "$VERSION" || {
    echo "Az exe-ben nem $VERSION a verzió – a build hibás." >&2
    exit 1
}

NOTES="$(git log --no-merges --format='- %s' ${PREV_TAG:+"$PREV_TAG"..}"$TAG")"
git push origin HEAD
git push origin "$TAG"
"$GH" release create "$TAG" dist/MailTicker.exe --title "Mail Ticker $VERSION" --notes "$NOTES"
echo ">> Kiadva: $TAG"
