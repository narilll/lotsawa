# Lotsawa

A Claude Code skill for translating Tibetan Buddhist texts (sadhanas, prayers,
smoke offerings), optionally alongside an English translation, into a
configurable target language. Translation runs as a multi-agent workflow with
the main session as editor-in-chief. Output is `text.md` in the skill's
interlinear format.

## Roles

| Role | Does |
|---|---|
| `translator` | Produces the full draft from the Tibetan (and/or the English). |
| `translator_2` | A second, independent full draft — Tibetan+English sources, texts over ~300 segments, or always with `always_two_drafts: true`. |
| `pandita` | Meaning consultant, asked on demand: answers the editor's numbered questions about the Tibetan (gloss, grammar, ritual context, confidence) and never writes the target language. |
| `reviewer` | Attacks the draft adversarially and reports only the segments it objects to, each with an alternative. |
| `terminologist` | Audits the draft(s) against the whole glossary and proposes new rows; never edits the glossary itself. |
| `backtranslator` | Glosses the target-language lines of a sample back into English, blind to the original — the check for silent meaning loss. |
| `proofreader` | Reads the finished target language alone, without the original, against the style guide. |
| `phonetics` | Supplies the phonetic transcription of Tibetan lines and mantras. |

## Contents

| File | Purpose |
|---|---|
| `SKILL.md` | Skill definition — the full workflow, format and terminology rules |
| `lotsawa.yaml` | Default configuration: target language, thresholds, roles → models |
| `glossary.tsv` | Default terminology glossary (Tibetan/Wylie → target) |
| `phonetics.md` | Default phonetic transcription rules |
| `style.md` | Default style guide |
| `scripts/lotsawa.py` | Mechanical steps: segmentation, draft comparison, assembly, lint |
| `scripts/segment_lotsawa_epub.py` | Segmentation of EPUB sources |

## Install

```
git clone https://github.com/narilll/lotsawa .claude/skills/lotsawa
python3 .claude/skills/lotsawa/scripts/lotsawa.py selftest
```

## Defaults and overrides

`lotsawa.yaml`, `glossary.tsv`, `phonetics.md`, and `style.md` in the skill
root are the defaults and apply always. A same-name file in the project root
(the directory Claude Code runs in) overrides it. `lotsawa.yaml` merges
shallowly over the default: top-level keys replace, `roles` merge per role,
and any key you don't specify is inherited. The scripts pick up `./glossary.tsv`
if it exists in the project root, otherwise fall back to the skill default.

The `dharmamitra` companion skill (sibling directory `skills/dharmamitra`) can
be enabled for the pandita with `pandita_tools: [dharmamitra]`; it calls
dharmamitra.org sparingly, under the ethics rules in its own SKILL.md.

## Another target language

Copy the four files (`lotsawa.yaml`, `glossary.tsv`, `phonetics.md`,
`style.md`) to your project root and rewrite them, keeping the same
columns/sections. Set `target_language`. Recalibrate `max_expansion_ratio`
with `meter` on your own finished texts. Set `phonetics_lint: false` unless
you keep the Czech transcription rules.

## Cross-model cast (optional)

For users with GitHub Copilot CLI and Codex, a project-level `lotsawa.yaml`
override can put roles on different model families:

```yaml
roles:
  translator:   {backend: copilot, model: gemini-3.1-pro-preview, effort: high, fallback: {backend: agent, model: opus}}
  translator_2: {backend: codex}
  reviewer:     {backend: codex, fallback: {backend: agent, model: opus}}
```

Each role runs on a different model family so one model's systematic error is
caught by another; any role left unspecified keeps the defaults.

## Batch folders

When a folder already holds finished `text.md` files, `build --reuse <folder>`
and `consist --corpus <folder>` reuse and cross-check them — see SKILL.md for
details.
