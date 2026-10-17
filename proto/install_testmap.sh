#!/usr/bin/env bash
# Install converted maps into a private ToEE overlay's module folder (loose files override ToEE.dat).
# Usage: MES_SRC=<dir> install_testmap.sh <outdir> <overlay game dir> AREA...   (local testing only; never ship the output)
# MES_SRC must hold the vanilla art/ground/ground.mes, rules/MapList.mes and mes/map_names.mes extracted from your own
# ToEE .dat files (any DAT extractor); the converter's snippets are appended to copies of them.
set -e
OUT=$1; G=$2; shift 2
: "${MES_SRC:?set MES_SRC to a folder with the vanilla ground.mes / MapList.mes / map_names.mes}"
M=$G/modules/ToEE
mkdir -p "$M/maps" "$M/art/ground" "$M/art/clip" "$M/rules" "$M/mes"
cp "$MES_SRC/art/ground/ground.mes" "$M/art/ground/ground.mes"; cp "$MES_SRC/rules/MapList.mes" "$M/rules/MapList.mes"
cp "$MES_SRC/mes/map_names.mes" "$M/mes/map_names.mes"
for A in "$@"; do
  rm -rf "$M/maps/$A" "$M/art/ground/$A" "$M/art/clip/$A" "$M/art/ground/${A}_doors" "$M/art/ground/${A}_night"
  cp -r "$OUT/maps/$A" "$M/maps/"; cp -r "$OUT/art/ground/$A" "$M/art/ground/"; cp -r "$OUT/art/clip/$A" "$M/art/clip/"
  [ -d "$OUT/art/ground/${A}_doors" ] && cp -r "$OUT/art/ground/${A}_doors" "$M/art/ground/"
  [ -d "$OUT/art/ground/${A}_night" ] && cp -r "$OUT/art/ground/${A}_night" "$M/art/ground/"
  awk '/^# /{s=($0 ~ "ground.mes")} !/^#/ && s' "$OUT/${A}_snippets.txt" | sed 's/$/\r/' >> "$M/art/ground/ground.mes"
  awk '/^# /{s=($0 ~ "MapList")} !/^#/ && s' "$OUT/${A}_snippets.txt" | sed 's/$/\r/' >> "$M/rules/MapList.mes"
  awk '/^# /{s=($0 ~ "map_names")} !/^#/ && s' "$OUT/${A}_snippets.txt" | sed 's/$/\r/' >> "$M/mes/map_names.mes"
done
tail -n 4 "$M/rules/MapList.mes" "$M/art/ground/ground.mes" "$M/mes/map_names.mes"
