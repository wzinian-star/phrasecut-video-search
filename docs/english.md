# PhraseCut · Video Quote Search

PhraseCut searches timed dialogue for a word or phrase and returns the source edition, time range, line, context and evidence. It runs offline with Python 3.9+ and the standard library. Download and unzip the repository, open a terminal in its root, and try either real example.

```sh
python3 phrasecut.py search 'Find 1 English clip saying “could be dying”'
python3 phrasecut.py search 'te quiero' --lang es --limit 2
```

In the English example, seek to **05:34.000–05:39.500** in *ECAM 2018*. The speaker says “He could be dying.” The source page had Spanish text, while the local recording contained English speech. A second offline transcription of the exported interval confirmed the phrase. The local sample started 334 seconds into the source. [Watch at Mediateca de EducaMadrid](https://mediateca.educa.madrid.org/video/s676kx3asrhxjy77)

The Spanish case began as a request for 20 film or TV scenes with “te quiero.” The edit grew to 50 excerpts, each from a distinct publisher page, across 18 works. The catalogue gives times relative to each linked excerpt. [Browse all 50 sources](te-quiero.md)

## Browse before installing

The creator’s Spanish video series now has **105 catalogued excerpts from 95 distinct source pages**. Browse [Vale](screening-room.md#vale), [No pasa nada](screening-room.md#no-pasa-nada), [birthday wishes](screening-room.md#birthday), [No me jodas](screening-room.md#no-me-jodas), [Gilipollas](screening-room.md#gilipollas), [Qué cojones](screening-room.md#que-cojones) or [Te quiero](te-quiero.md). Each table gives times in the linked source edition. The birthday selection has 17 instances of *feliz cumpleaños* and three of *cumpleaños feliz*. Search the two word orders separately.

```sh
python3 phrasecut.py search 'no pasa nada' --lang es --limit 3
```

## Bring a subtitle track

```sh
python3 phrasecut.py index examples/studio-notes.vtt --title "Studio notes" --lang en --source studio-demo --out studio-index.json
python3 phrasecut.py search 'Find 2 English clips saying “wide shot”' --supplement studio-index.json
```

The bundled studio track is a written example of SRT/WebVTT import. Expect one hit and a shortfall of one. For your own captions, supply the language of the original speech and a stable source link or media identifier. Use an original-language track. A translated caption can suggest a scene, but does not establish the spoken words. Add regular indexes using repeated `--index` options. Order optional indexes with `--supplement`; PhraseCut stops opening them once the requested count is met. A search with no count checks all supplied indexes.

## Review and cut

```sh
python3 phrasecut.py search 'te quiero' --lang es --limit 2 --html > review.html
python3 phrasecut.py search 'te quiero' --lang es --limit 2 --json
python3 phrasecut.py clip rumbos-source.mp4 rumbos-line.mp4 --start 8.38 --end 12.63
```

Open the HTML file to inspect and follow results. Cutting requires a matching local source file, FFmpeg and ffprobe. Supply a fresh output filename and use media you have permission to edit. Search uses normalized, ordered words inside one cue. Real source validation covers English and Spanish. The CLI understands a literal phrase or a quoted phrase inside a request; the [project Skill](../.agents/skills/phrasecut/SKILL.md) can also interpret genre and context preferences and organize bounded follow-up research.

| Evidence | Meaning |
| --- | --- |
| `subtitle` | The original-language caption supplies a textual lead and adjacent cues. |
| `edit-transcript` | The editor recorded the line. The searched words lack a matching audio check. |
| `audio-asr` | An offline transcription of this interval contains the queried words. This label applies to the matched phrase. |

Film footage stays with the original publishers. The screenshot shows the tool's own review page. [Project and creator](https://github.com/wzinian-star/phrasecut-video-search)
