---
name: phrasecut
description: Find words or phrases actually spoken in videos. Search timed dialogue and subtitle indexes, report source-relative timecodes and evidence, and optionally cut a selected local video excerpt.
---

Use the repository root (the directory containing `phrasecut.py`). Resolve a natural-language request into the exact phrase, spoken language if specified, requested count, medium, and desired context. Keep the user's original spelling and contractions.

1. Run `python3 phrasecut.py search "PHRASE" --lang LANG --limit N --json` with the applicable options. Use `--index FILE` for the user's existing catalogues. For an additional same-language SRT/VTT track, run the documented `index` command once. Reuse its JSON thereafter. Pass extra indexes in priority order with `--supplement` to stop when the gap closes.
2. Inspect the returned line, source, context and edition-relative interval. Apply genre and intent preferences yourself. The CLI only filters text, count and language. Count accepted segments, distinct source URLs and works separately. After editorial filtering, recalculate the shortfall.
3. If short, search only the missing number. Use an authorized local subtitle collection first. If web research is permitted, cap candidate pages before starting, try the exact phrase on publisher pages, and check for an original-language timed track. Retain its source and timing. A translated subtitle or an untimed page quote is a lead. Keep unresolved leads separate. Reuse a prior verification for the same phrase, source edition and interval. Validate only the selected seconds if an authorized source file is available.
4. Return a source link, start and end, original words, available adjacent cues or labeled scene context, and evidence per result. `audio-asr` means the target phrase occurred in an audio transcription. `edit-transcript` and `subtitle` retain their original evidence levels. Report unavailable context, uncertain audio and missing results plainly. Direct the viewer to seek in the linked excerpt.
5. When editing is requested, use `clip` on the matching authorized local edition. Full-source times and times in a trimmed copy have different origins. Export to a fresh filename. A catalogue entry supplies location and attribution; publication rights depend on the media.
