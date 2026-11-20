import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import phrasecut as pc


class PhraseSearch(unittest.TestCase):
    def setUp(self):
        self.catalog = [pc.DATA / "spanish.json", pc.DATA / "english.json"]

    def test_exact_case_counts_and_evidence(self):
        report = pc.search("找 3 段西语里说「TE QUIERO」的片段", self.catalog)
        self.assertEqual((report["available"], report["source_pages"], report["titles"]), (50, 50, 18))
        self.assertEqual(len(report["results"]), 3)
        self.assertEqual({r["evidence"] for r in report["results"]}, {"audio-asr"})
        self.assertEqual(pc.search("su mujer", self.catalog)["results"][0]["evidence"], "edit-transcript")

    def test_screening_room_in_default_cli(self):
        def results(phrase):
            command = [sys.executable, str(pc.ROOT / "phrasecut.py"), "search", phrase, "--lang", "es", "--json"]
            return json.loads(subprocess.check_output(command, text=True))

        report = results("no pasa nada")
        self.assertEqual((report["available"], report["source_pages"]), (10, 10))
        scene, = (r for r in report["results"] if r["title"] == "Inevitable")
        self.assertEqual((scene["start"], scene["end"]), (98.96, 102.19))
        self.assertEqual(results("vale")["source_pages"], 9)
        self.assertEqual(results("no me jodas")["available"], 5)
        for phrase in ("gilipollas", "qué cojones"):
            rows = results(phrase)["results"]
            self.assertEqual(len(rows), 5)
            self.assertEqual({r["evidence"] for r in rows}, {"edit-transcript"})
        for phrase, count in [("feliz cumpleaños", 17), ("cumpleaños feliz", 3)]:
            verified = [r for r in results(phrase)["results"] if r["evidence"] == "audio-asr"]
            self.assertEqual(len(verified), count)

    def test_real_english_source_clock(self):
        row, = pc.search("Find 1 English clip saying “could be dying”", self.catalog)["results"]
        self.assertEqual((row["start"], row["end"]), (334, 339.5))
        self.assertEqual(row["evidence"], "audio-asr")

    def test_phrase_boundaries(self):
        self.assertFalse(pc.expression("te quiero").search("este quiero"))
        self.assertFalse(pc.expression("no me jodas").search("no jodas, hermano"))
        self.assertTrue(pc.expression("I’m good").search(pc.normalized("I'M GOOD!")))
        self.assertFalse(pc.expression("he").search("she"))
        self.assertTrue(pc.expression("你好").search("他说你好呀"))
        self.assertFalse(pc.expression("he could").search("he really could"))

    def test_subtitle_context_dedup_and_gap(self):
        with tempfile.TemporaryDirectory() as temp:
            index = Path(temp) / "extra.json"
            rows = pc.captions(pc.ROOT / "examples/studio-notes.vtt", "Studio", "en", "studio")
            index.write_text(json.dumps(rows))
            report = pc.search('Find 2 English clips saying “wide shot”', self.catalog, supplements=[index, index])
            self.assertEqual((report["available"], report["missing"]), (1, 1))
            row, = report["results"]
            self.assertEqual(row["evidence"], "subtitle")
            self.assertIn("lens", row["before"])
            self.assertIn("dancer", row["after"])
            skipped = pc.search('找 1 段西语「te quiero」', self.catalog, supplements=[index])
            self.assertNotIn(index.name, skipped["indexes_checked"])

    def test_srt_multiline_bom(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "a.srt"
            path.write_bytes(b'\xef\xbb\xbf1\r\n01:02:03,200 --> 01:02:05,100\r\n<i>Hello</i>\r\nthere!\r\n')
            row, = pc.captions(path, "Demo", "en", "demo")
            self.assertEqual((row["start"], row["text"]), (3723.2, "Hello there!"))

    def test_invalid_or_empty_tracks(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "empty.vtt"
            for contents in ["WEBVTT\n", "1\n00:01.900 --> 00:00.300\nBad"]:
                path.write_text(contents)
                with self.assertRaises(ValueError):
                    pc.captions(path, "title", "en", "src")

    def test_cli_index_reuse_and_protect_existing(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "index.json"
            cmd = [sys.executable, str(pc.ROOT / "phrasecut.py"), "index",
                   str(pc.ROOT / "examples/studio-notes.vtt"), "--lang", "en", "--title", "Studio",
                   "--source", "my-studio", "--out", str(target)]
            subprocess.run(cmd, check=True, capture_output=True)
            stamp = target.stat().st_mtime_ns
            self.assertIn("Reused", subprocess.check_output(cmd, text=True))
            self.assertEqual(stamp, target.stat().st_mtime_ns)
            target.write_text("keep this")
            self.assertNotEqual(subprocess.run(cmd, capture_output=True).returncode, 0)
            self.assertEqual(target.read_text(), "keep this")

    def test_protect_clip_destination(self):
        with tempfile.TemporaryDirectory() as temp:
            media = Path(temp) / "my.mp4"
            media.write_bytes(b"original")
            with self.assertRaises(FileExistsError):
                pc.clip(media, media, 0, 1)
            self.assertEqual(media.read_bytes(), b"original")
            with patch("phrasecut.subprocess.check_output", return_value="5"):
                with self.assertRaises(ValueError):
                    pc.clip(media, Path(temp) / "out.mp4", 4, 9)

    def test_html_escapes_and_limits_links(self):
        report = pc.search("te quiero", self.catalog, limit=1)
        report["results"][0].update(title="<script>", source="javascript:alert(1)")
        page = pc.html_report(report)
        self.assertIn("&lt;script&gt;", page)
        self.assertNotIn('href="javascript:', page)


if __name__ == "__main__":
    unittest.main()
