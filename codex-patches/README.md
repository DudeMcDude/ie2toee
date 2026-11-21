# Codex patches for the IWD2 (iwd2-targos) converter

ChatGPT Codex kept these on Shai's PC as patch files for the IWD2 preview builds. They target
`proto/ie2toee_preview_iwd2.py` and related files on the `iwd2-targos` branch, not `main`, and have
not been committed to any branch yet. (`iwd2-preview-rebuild.patch` is already on `iwd2-targos` via PR #2,
so it is not included.)

Apply them to `origin/iwd2-targos` (725f954) in this order:

1. iwd2-scripted-containers.patch
2. iwd2-palisade-visibility.patch
3. iwd2-starting-equipment.patch
4. iwd2-chapter-quests.patch
5. iwd2-map-alerts.patch

Steps 1-4 apply cleanly with `git apply` (checked 2026-11-21). Step 5 conflicts at the top of
`proto/ie2toee_preview_iwd2.py`, so it needs a manual merge. It adds `ie_map_alerts.py` and
`guidance/map_alerts.json`, and both of those already exist on this branch.
