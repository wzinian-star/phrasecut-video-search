"""Search reusable video dialogue indexes and cut a selected local interval."""
import argparse
import html
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unicodedata
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "docs" / "data"
TIMING = re.compile(r'((?:\d+:)?\d{2}:\d{2}[.,]\d{3})\s+-->\s+((?:\d+:)?\d{2}:\d{2}[.,]\d{3})(?:\s+.*)?')
QUOTES = re.compile(r'“([^”]+)”|「([^」]+)」|«([^»]+)»|"([^"]+)"')
LANGUAGES = {"西语": "es", "西班牙语": "es", "spanish": "es", "英语": "en", "英文": "en", "english": "en"}


def normalized(value):
    return unicodedata.normalize("NFKC", value).casefold().replace("’", "'")


def expression(phrase):
    words = re.findall(r"\w+(?:'\w+)*", normalized(phrase))
    if not words:
        raise ValueError("Enter a spoken word or phrase.")
    pattern = r"[^\w']+".join(map(re.escape, words))
    # 中日韩连续文字没有空格词界；拉丁字母保留整词边界。
    cjk = r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]"
    left = "" if re.match(cjk, words[0][0]) else r"(?<![\w'])"
    right = "" if re.match(cjk, words[-1][-1]) else r"(?![\w'])"
    return re.compile(left + pattern + right)


def request_parts(query, language, limit):
    match = QUOTES.search(query)
    phrase = next(v for v in match.groups() if v) if match else query.strip()
    if match:
        prompt = normalized(query[:match.start()] + " " + query[match.end():])
        language = language or next((v for k, v in LANGUAGES.items() if k in prompt), None)
        count = re.search(r'(\d+)\s*(?:段|个|条|(?:english |spanish )?(?:clips?|examples?)\b)', prompt)
        if limit is None and count:
            limit = int(count[1])
    if limit is not None and limit < 1:
        raise ValueError("The requested number of clips must be positive.")
    return phrase, language, limit


def seconds(stamp):
    parts = stamp.replace(",", ".").split(":")
    if float(parts[-1]) >= 60 or len(parts) == 3 and int(parts[-2]) >= 60:
        raise ValueError(f"Invalid timestamp: {stamp}")
    result = 0.0
    for part in parts:
        result = result * 60 + float(part)
    return result


def clock(value):
    total = round(value * 1000)
    mins, ms = divmod(total, 60000)
    return f"{mins:02d}:{ms // 1000:02d}.{ms % 1000:03d}"


def interval(start, end):
    if not (math.isfinite(start) and math.isfinite(end) and 0 <= start < end):
        raise ValueError(f"Invalid interval: {start} to {end}")


def captions(path, title, language, source):
    rows = []
    for block in re.split(r"\n[ \t]*\n", path.read_text(encoding="utf-8-sig").strip()):
        lines = block.strip().splitlines()
        if not lines or lines[0].split()[0] in {"WEBVTT", "NOTE", "STYLE", "REGION"}:
            continue
        index = next((i for i, line in enumerate(lines[:2]) if "-->" in line), None)
        if index is None or not (times := TIMING.fullmatch(lines[index].strip())):
            raise ValueError(f"Invalid subtitle block: {lines[0]}")
        start, end = (seconds(v) for v in times.groups())
        interval(start, end)
        text = html.unescape(re.sub(r"<[^>]+>", "", " ".join(lines[index+1:]))).strip()
        if text:
            rows.append(dict(title=title, language=language, source=source, start=start, end=end,
                             text=text, evidence="subtitle"))
    if not rows:
        raise ValueError("No subtitle cues found.")
    rows.sort(key=lambda row: row["start"])
    for i, row in enumerate(rows):
        row["before"] = rows[i-1]["text"] if i else ""
        row["after"] = rows[i+1]["text"] if i+1 < len(rows) else ""
    return rows


def search(query, indexes, language=None, limit=None, supplements=()):
    phrase, language, limit = request_parts(query, language, limit)
    pattern = expression(phrase)
    found = {}
    indexes = list(dict.fromkeys(indexes))
    checked = []
    for path in dict.fromkeys([*indexes, *supplements]):
        if path not in indexes and limit is not None and len(found) >= limit:
            break
        checked.append(path.name)
        for item in json.loads(path.read_text(encoding="utf-8")):
            if language and item["language"].casefold() != language.casefold():
                continue
            if not pattern.search(normalized(item["text"])):
                continue
            interval(item["start"], item["end"])
            row = item.copy()
            # 旧制作记录只核实过目标短语，其他命中沿用编辑台词证据。
            if row["evidence"] == "audio-asr":
                heard = row.get("asr_text", "")
                if not pattern.search(normalized(heard)):
                    row["evidence"] = "edit-transcript"
            key = (row["source"], round(row["start"]*1000), round(row["end"]*1000), row["language"])
            rank = {"subtitle": 0, "edit-transcript": 1, "audio-asr": 2}
            if key not in found or rank[row["evidence"]] > rank[found[key]["evidence"]]:
                found[key] = row
    rows = list(found.values())
    return {
        "indexes_checked": checked, "query": query, "phrase": phrase, "language": language,
        "source_pages": len({r["source"] for r in rows}), "titles": len({r["title"] for r in rows}),
        "available": len(rows), "requested": limit, "missing": max(0, limit-len(rows)) if limit else 0,
        "results": rows[:limit],
    }


def display(report):
    print(f'{report["phrase"]}  |  {report["available"]} matches  |  {len(report["results"])} shown')
    for row in report["results"]:
        print(f'\n{row["title"]}  {clock(row["start"])} – {clock(row["end"])}  [{row["evidence"]}]')
        for key, label in (("before","Before"), ("text","Line"), ("after","After"),
                           ("translation","Translation"), ("context","Context")):
            if row.get(key):
                print(f'  {label}: {row[key]}')
        print(f'  Source: {row["source"]}')
    if report["missing"]:
        print(f'Still needed: {report["missing"]}. Look for this phrase in additional caption tracks.')


def html_report(report):
    escape = html.escape
    rows = report["results"]
    cards = []
    for row in rows:
        source = row["source"]
        publisher = urlsplit(source)
        label = escape(publisher.hostname or source)
        link = (f'<a href="{escape(source, quote=True)}">{label} ↗</a>'
                if publisher.scheme in {"http", "https"} and publisher.hostname else label)
        context = " ".join(f'{label}: {row[key]}' for key, label in (("before", "Before"), ("after", "After"))
                           if row.get(key))
        if row.get("context"):
            context = (context + " " + row["context"]).strip()
        translation = f'<p lang="zh">{escape(row["translation"])}</p>' if row.get("translation") else ""
        cards.append(f'<article><div class="meta"><time>{clock(row["start"])} – {clock(row["end"])}</time>'
                     f'<span>{escape(row["evidence"])}</span></div><h2>{escape(row["title"])}</h2>'
                     f'<blockquote>{escape(row["text"])}</blockquote>{translation}'
                     f'<p class="context">{escape(context)}</p>{link}</article>')
    totals = (f'{report["available"]} matching excerpts · {report["source_pages"]} source pages · '
              f'{report["titles"]} titles · showing {len(rows)}')
    missing = f'<p>Still needed: {report["missing"]}</p>' if report["missing"] else ""
    css = """
    *{box-sizing:border-box}body{margin:0;background:#f8f6ef;color:#202d29;font:17px/1.52 system-ui,sans-serif}
    main{max-width:980px;margin:auto;padding:30px 40px 55px}header{display:flex;justify-content:space-between;
    align-items:baseline;gap:16px;border-bottom:2px solid #243830;padding-bottom:12px}
    header b{font-size:24px;letter-spacing:-1.5px}header small,.meta,time{font-family:ui-monospace,monospace}
    h1,h2,blockquote{font-family:Georgia,serif}h1{font-size:clamp(44px,8vw,80px);line-height:1.1;
    font-weight:normal;margin:24px 0 6px;overflow-wrap:anywhere} .summary{color:#506057;margin:0 0 22px}
    article{padding:18px 24px;margin:15px 0;background:#fffefa;border:1px solid #c3cabf;border-left:4px solid #236147}
    .meta{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;color:#305c47;font-size:14px}
    .meta span{background:#dfede1;border-radius:4px;padding:2px 8px}h2{font-size:27px;margin:8px 0}
    blockquote{font-size:21px;margin:0}article p{margin:6px 0}.context{color:#526059;font-size:15px}
    a{color:#245b44;font-size:15px;text-underline-offset:3px}@media(max-width:600px){main{padding:18px 14px}
    article{padding:13px 14px}header small{font-size:11px}}
    """
    return (f'<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" '
            f'content="width=device-width,initial-scale=1"><title>PhraseCut · {escape(report["phrase"])}</title>'
            f'<style>{css}</style><main><header><b>PhraseCut</b><small>VIDEO QUOTE SEARCH</small></header>'
            f'<p>{escape(report["query"])}</p><h1>“{escape(report["phrase"])}”</h1><p class="summary">{totals}</p>'
            f'{"".join(cards)}{missing}</main></html>')


def clip(media, output, start, end):
    interval(start, end)
    if not media.is_file() or output.suffix.lower() != ".mp4":
        raise ValueError("Supply a local video file and a new .mp4 output path.")
    if output.exists():
        raise FileExistsError(output)
    source = str(media.resolve())
    duration = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                        "-of", "csv=p=0", source], text=True)
    if end > float(duration) + 0.001:
        raise ValueError("Interval exceeds this media edition.")
    with tempfile.TemporaryDirectory(dir=output.parent) as folder:
        new = Path(folder) / "clip.mp4"
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", str(start), "-i", source,
                        "-t", str(end-start), "-map", "0:v:0", "-map", "0:a:0?", "-c:v", "libx264",
                        "-pix_fmt", "yuv420p", "-c:a", "aac", "-movflags", "+faststart", str(new)], check=True)
        os.link(new, output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    find = sub.add_parser("search", help="Find a literal phrase or a quoted phrase in a request")
    find.add_argument("query")
    find.add_argument("--lang")
    find.add_argument("--limit", type=int)
    find.add_argument("--index", type=Path, action="append", default=[], help="Add an index; repeatable")
    find.add_argument("--supplement", type=Path, action="append", default=[],
                      help="Search this additional index only while the requested count is short; repeatable")
    output = find.add_mutually_exclusive_group()
    output.add_argument("--json", action="store_true")
    output.add_argument("--html", action="store_true", help="Print a self-contained review page")
    add = sub.add_parser("index", help="Convert one same-language SRT/VTT track into a reusable index")
    add.add_argument("subtitle", type=Path)
    for key in ["title", "lang", "source"]:
        add.add_argument("--" + key, required=True)
    add.add_argument("--out", type=Path, required=True)
    cut = sub.add_parser("clip", help="Export a source-relative interval from a local video")
    cut.add_argument("media", type=Path)
    cut.add_argument("output", type=Path)
    cut.add_argument("--start", required=True, type=float)
    cut.add_argument("--end", required=True, type=float)
    args = parser.parse_args()
    if args.command == "search":
        paths = [DATA / "spanish.json", DATA / "english.json", DATA / "screening-room.json", *args.index]
        report = search(args.query, paths, args.lang, args.limit, args.supplement)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        elif args.html:
            print(html_report(report))
        else:
            display(report)
    elif args.command == "index":
        rows = captions(args.subtitle, args.title, args.lang, args.source)
        data = json.dumps(rows, ensure_ascii=False, indent=2) + "\n"
        if args.out.exists() and args.out.read_text(encoding="utf-8") == data:
            print(f"Reused {len(rows)} cues.")
            return
        with tempfile.TemporaryDirectory(dir=args.out.parent) as folder:
            new = Path(folder) / "index.json"
            new.write_text(data, encoding="utf-8")
            os.link(new, args.out)
        print(f"Indexed {len(rows)} cues.")
    else:
        clip(args.media, args.output, args.start, args.end)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
        sys.exit(f"phrasecut: {error}")
