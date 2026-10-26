#!/usr/bin/env bash
# Engine-side path node + clearance bake for converted maps (pipeline step after ie_pathnodes.py).
# Runs a Temple+ build with the TP_AUTOLOAD/TP_AUTOEXEC harness and debug.bake_pathnodes (DudeMcDude/TemplePlus
# feature/pathnode-bake) via run_ingame.sh: every area of the travel data is loaded in turn and gets
# pathnodenew.pnd / pathnodedist.pnd (neighbours recalculated with the real pathfinder) and clearance.bin.
# Usage: TP_DIST=.. TOEE_DIR=.. TOEE_OVERLAY=.. ./pathnode_bake.sh <ie_travel_data.py> [areas...]
#   Bakes into $TOEE_OVERLAY/modules/ToEE/maps/<area>/ (the copy the engine loads); PNBAKE_COPY_TO=<maps dir> also
#   copies the results there (e.g. the build output). Stale baked files are removed first so the fresh pathnode.pnd is used.
set -eu
: "${TOEE_DIR:?set TOEE_DIR}" "${TOEE_OVERLAY:?set TOEE_OVERLAY}" "${TP_DIST:?set TP_DIST}"
HERE=$(cd "$(dirname "$0")" && pwd); TRAVEL=$1; shift
[ "$(realpath -m "$TOEE_DIR")" != "$(realpath -m "$TOEE_OVERLAY")" ] || { echo 'pathnode_bake: TOEE_DIR must be a separate ToEE copy (run_ingame.sh restores the overlay saves from it)'; exit 2; }
MAPS=$TOEE_OVERLAY/modules/${PNBAKE_MODULE:-ToEE}/maps
JOBS=$(python3 - "$TRAVEL" "$@" <<'PY'
import sys, importlib.util
s = importlib.util.spec_from_file_location('t', sys.argv[1]); m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
want = sys.argv[2:] or sorted(m.AREAS)
out = []
for a in want:
    d = m.AREAS[a]; e = list(d['entrances'].values())
    if e: out.append('%s:%d:%d,%d' % (a, d['map'], e[0][0], e[0][1]))
print(';'.join(out))
PY
)
for j in ${JOBS//;/ }; do rm -f "$MAPS/${j%%:*}"/{pathnodenew.pnd,pathnodedist.pnd,clearance.bin}; done
export IE2TOEE_PNBAKE="$JOBS" IE2TOEE_PNBAKE_OUT="Z:${MAPS//\//\\}"
export TP_AUTOEXEC="import sys; sys.path[:0]=['Z:$HERE']; import ingame_pathnode_bake"
IE_OUT=${IE_OUT:-/tmp/pnbake_out}; export IE_OUT
"$HERE/run_ingame.sh" pnbake ${PNBAKE_SECS:-600}
grep -a PNBAKE "$IE_OUT/ingame/probe.log" || true
n=$(grep -ac "PNBAKE .* OK" "$IE_OUT/ingame/probe.log" || true); want=$(echo "$JOBS" | tr ';' '\n' | grep -c .)
if [ -n "${PNBAKE_COPY_TO:-}" ]; then
  for j in ${JOBS//;/ }; do a=${j%%:*}; mkdir -p "$PNBAKE_COPY_TO/$a"; cp -f "$MAPS/$a"/{pathnodenew.pnd,pathnodedist.pnd,clearance.bin} "$PNBAKE_COPY_TO/$a/" 2>/dev/null || true; done
fi
echo "pathnode_bake: $n/$want areas baked"; [ "$n" = "$want" ]
