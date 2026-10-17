#!/usr/bin/env bash
# In-game test runner (developer tool). Runs a Temple+ build that has the TP_AUTOLOAD / TP_AUTOEXEC test harness in a
# private wine prefix against a private ToEE overlay copy, executes a probe script inside the game and takes a
# screenshot on every "SHOT <name>" line the probe writes. Kills only this prefix's wineserver.
#
# Usage: TP_DIST=<Temple+ dist dir> TOEE_DIR=<vanilla ToEE> TOEE_OVERLAY=<overlay copy> ./run_ingame.sh <tag> [secs]
#   optional: WINEPREFIX (default ~/.wine-toee-ie), IE_OUT (default ../out), TP_AUTOEXEC (default: import ingame_probe)
# Screenshots/logs go to $IE_OUT/ingame/<tag>/ (derived from the player's files: local only).
set -u
TAG=${1:-run}; SECS=${2:-240}
HERE=$(cd "$(dirname "$0")" && pwd)
: "${TP_DIST:?set TP_DIST}" "${TOEE_DIR:?set TOEE_DIR}" "${TOEE_OVERLAY:?set TOEE_OVERLAY}"
IE_OUT=$(realpath -m "${IE_OUT:-$HERE/../out}")
export WINEPREFIX=${WINEPREFIX:-$HOME/.wine-toee-ie} DISPLAY=${DISPLAY:-:2} WINEDEBUG=-all WINEDLLOVERRIDES=winedbg.exe=d
OUT=$IE_OUT/ingame/$TAG; mkdir -p "$OUT"
P=$IE_OUT/ingame/probe.log; rm -f "$P"
export IE2TOEE_PROBE_LOG="Z:$P"
L="$WINEPREFIX/drive_c/users/$USER/Saved Games/TemplePlus/TemplePlus.log"; rm -f "$L"
fresh_saves() {   # the probes teleport and autosave (pickling their time events): restore the original saves each run
  rm -rf "$TOEE_OVERLAY/modules/ToEE/Save" && cp -a "$TOEE_DIR/modules/ToEE/Save" "$TOEE_OVERLAY/modules/ToEE/"
}
wineserver -k 2>/dev/null; sleep 0.3
fresh_saves
export TP_AUTOLOAD=${TP_AUTOLOAD:-SlotAuto}
export TP_AUTOEXEC=${TP_AUTOEXEC:-"import sys; sys.path[:0]=['Z:$HERE', 'Z:$HERE/runtime', 'Z:$IE_OUT']; import ingame_probe"}
cd "$TP_DIST"
wine explorer /desktop=ToEEie,1280x800 TemplePlus.exe > "$OUT/wine.out" 2>&1 &
T0=$(date +%s); SEEN=0
while [ $(( $(date +%s) - T0 )) -lt "$SECS" ]; do
  sleep 0.3
  if [ -f "$P" ]; then
    N=$(wc -l < "$P")
    if [ "$N" -gt "$SEEN" ]; then
      sed -n "$((SEEN+1)),${N}p" "$P" | tr -d "\r" | while read -r line; do
        case "$line" in SHOT\ *) import -display "$DISPLAY" -window root "$OUT/${line#SHOT }.bmp" 2>/dev/null; echo "shot ${line#SHOT }";; esac
      done
      SEEN=$N
      grep -q '^DONE' "$P" && break
    fi
  fi
done
import -display "$DISPLAY" -window root "$OUT/final.png" 2>/dev/null
wineserver -k 2>/dev/null; sleep 1
fresh_saves
cp "$L" "$OUT/TemplePlus.log" 2>/dev/null; cp "$P" "$OUT/" 2>/dev/null
for f in "$OUT"/*.bmp; do [ -e "$f" ] && convert "$f" -crop 1290x830+0+0 +repage "${f%.bmp}.png" && rm "$f"; done
echo "elapsed $(( $(date +%s) - T0 ))s; log lines $(wc -l < "$OUT/TemplePlus.log" 2>/dev/null)"
