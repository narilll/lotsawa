---
name: lotsawa
description: Use when the user asks to translate a Tibetan and/or English Buddhist practice text (sadhana, prayer, offering) into the target language set by the skill's `lotsawa.yaml` or the project's override. Input is a file (EPUB, md, txt) or pasted text; output is an interlinear `text.md`.
---

# Lotsawa — Tibetan/English → target language

You (the main session) are the reviewer and editor-in-chief. You never translate alone and never accept a single draft
unchecked: a translator produces the draft, an adversarial reviewer attacks it, a back-translation pass tests a sample for
silent meaning loss, a proofreader reads the target language alone, and you decide every contested segment and assemble the
final text. Where an English translation exists, four full drafts replace the reviewer.

Every format rule this skill needs is defined below; target-language rules live in the four configuration files described
below. Do not depend on other files in the working folder existing — previously translated texts only add to the rules here,
never replace them. Mechanical steps (segmentation, comparison, assembly, lint) are done by `scripts/lotsawa.py` — **never write them inline
in Python.**

## Configuration

The skill is driven by four files. Each of them **ships with the skill and always applies**; a project overrides one by placing
a file of the same name in the **project root** — the directory Claude Code was started in. There is no search chain and no path
keys: either the project root has the file, or the skill default is used.

| File | Holds | Used as |
|---|---|---|
| `lotsawa.yaml` | settings and the role cast | Read by you (the main session); see the keys below |
| `glossary.tsv` | binding terminology | `glossary --prompt` (into every translator prompt) and `check` (drift report) |
| `phonetics.md` | transcription rules | Handed to the `phonetics` role |
| `style.md` | target-language style guide | Passed verbatim to translators and to the proofreader |

`lotsawa.yaml` keys:

| Key | Meaning |
|---|---|
| `target_language` | Language every draft is written in |
| `max_expansion_ratio` | Passed as `--max-ratio` to `check` and `meter` |
| `phonetics_lint` | `true` → pass `--pho-lint` to `build` |
| `always_two_drafts` | `true` → `translator_2` runs for **every** text, not only Tibetan+English sources and texts over ~300 segments |
| `pandita_tools` | List of companion skill directories the `pandita` may consult (e.g. `[dharmamitra]`); empty = the pandita works from the Tibetan alone |
| `roles` | Per role: `backend`, `model`, optional `effort`, optional `fallback: {backend, model}` |

**Merge:** a project `lotsawa.yaml` is a shallow merge over the skill default — top-level keys replace, `roles` merge **per
role** (keys a project role does not specify are inherited), and any key the project omits keeps the default value. **The main
session applies a role's `fallback`** when the primary backend fails (quota, timeout) and records the substitution in
`drafts/notes.md`.

Override example — a project `lotsawa.yaml` that moves only the reviewer to Codex:

```yaml
roles:
  reviewer: {backend: codex, fallback: {backend: agent, model: opus}}
```

**At the start of every run, print one line naming the four files in effect** and whether each is the skill default or a project
override, e.g. `config: lotsawa.yaml (project), glossary.tsv (project), phonetics.md (default), style.md (default)`. Every edit
made during the work — a new glossary term, a new style bullet, a phonetics calibration — is written **to the file in effect**,
never to the skill default when a project override exists.

### Backend recipes

`agent` — Agent tool, `model: {model}`, `run_in_background: true`. The whole prompt goes into `drafts/prompt-<role>.md` and the
agent is told to read it.

`copilot`:

```bash
cd <project root>
SID=$(uuidgen)   # record in drafts/notes.md; enables follow-up questions
copilot -p "Read '<text>/drafts/prompt-<role>.md' and carry out the task exactly as written." \
  --model {model} --effort {effort} --allow-all-tools --no-color -s --log-level none \
  --session-id "$SID" > '<text>/drafts/<role>.job.log' 2>&1
```

- `--allow-all-tools` is **mandatory** — without it non-interactive mode does not run at all and the draft is never written.
- `--effort` values are model-specific and an unsupported value fails the run immediately; take the value from the role config,
  do not invent one — when the role has no `effort`, omit the flag.
- Run from the project root, not from the text subfolder. Never poll — `run_in_background` notifies you.
- Follow-up: `copilot --session-id "$SID" -p '<question>' --allow-all-tools -s --no-color`.

`codex` — `/sous-chef:fire`, one ticket per draft or per review, background jobs. **Do not set the model in the ticket**; it
comes from the codex config. Run from the project root — the `workspace-write` sandbox is bound to cwd and rejects writes
outside it, discarding the whole run. Add `--skip-git-repo-check` when the project is not a git repository. Never use
`/sous-chef:serve` — its taste/refire stages duplicate the comparison in Step 3. Follow-up = a short `fire` ticket.

After every delegation, arm one fallback wakeup (1200 s+) in case a job hangs, and cancel it once all drafts have landed.

### Role → file

| Role | Writes |
|---|---|
| `translator` | `drafts/translator-tib.md` / `drafts/translator-en.md` |
| `translator_2` | `drafts/translator_2-tib.md` / `drafts/translator_2-en.md` |
| `pandita` | `drafts/pandita.md` (Q&A log, **appended** per round — never overwritten) |
| `reviewer` | `drafts/review.md` (`review-A.md` / `review-B.md` when split) |
| `terminologist` | `drafts/terminology.md` |
| `backtranslator` | `drafts/backtrans.md` |
| `proofreader` | `drafts/proofread.md` |
| `phonetics` | `drafts/pho_done.txt` / `drafts/mantra_done.txt` |

`drafts/notes.md` records backend, model and session id per file.

## Pipeline

```
python3 <skill>/scripts/lotsawa.py segment original.md -o drafts/source.md
python3 <skill>/scripts/lotsawa.py glossary --prompt                       # binding terminology, regenerate before every launch
                                                                           # (the terminologist instead reads glossary.tsv directly, `open` rows included)
python3 <skill>/scripts/lotsawa.py compare --source drafts/source.md --draft A=drafts/translator-tib.md --draft B=drafts/translator_2-tib.md -o drafts/review-compare.md
python3 <skill>/scripts/lotsawa.py build --source drafts/source.md --base drafts/<base>.md --pho drafts/pho_done.txt [--mantra drafts/mantra_done.txt] [--pho-lint] -o text.md
python3 <skill>/scripts/lotsawa.py check text.md --original original.md --max-ratio <max_expansion_ratio>
python3 <skill>/scripts/lotsawa.py target text.md > drafts/target.txt      # target-language lines only, for the proofreader
python3 <skill>/scripts/lotsawa.py meter text.md --max-ratio <max_expansion_ratio>
python3 <skill>/scripts/lotsawa.py selftest                                # after any script edit
```

`check` and `glossary` resolve the glossary themselves (`./glossary.tsv` if the working directory has one, otherwise the skill
default; the path is printed as `note: glossary = …` on stderr) — add `--glossary <path>` only when the project's glossary lives
somewhere else. **Run the scripts from the project root**, so that resolution sees the project override.

Script rule: **data loss or corruption is fatal (exit 1), editorial judgment is a warning.** Exit 2 means "phonetics missing" —
not an error, the `*_todo.txt` files are written. Run `check` **after every manual edit** as well; that is where defects used to
escape.

## Two source shapes

| Source | Cast | When |
|---|---|---|
| **Tibetan only** (`original.md`, often one long line) | `translator` + `reviewer` + `backtranslator` | Default case. Wiki sources carry no English translation. |
| **Tibetan + English** (e.g. Lotsawa House EPUB) | four drafts: `translator-tib`, `translator-en`, `translator_2-tib`, `translator_2-en` | When the source carries an English translation — two source languages give real diversity of perspective. |

**Why two full drafts are not the default for Tibetan-only sources:** two models on an identical task diverge mostly in style,
while the hard places (technical ritual terminology) get flagged as uncertain by **both** — a failure that comparing drafts
cannot catch in principle. Role diversity replaces redundancy; two full drafts are paid for only where independent reading pays
off (root terms, main sadhanas, > 300 segments).

**`always_two_drafts: true` overrides this:** `translator_2` then always runs, whatever the source shape or length, and
`compare` always gets two drafts.

## Step 1 — Prepare the source

1. Load the input:
   - **Tibetan-only `original.md`** (most common): `lotsawa.py segment original.md -o drafts/source.md`. The script picks a
     delimiter (`༔` ≥ 2× → terma mode, otherwise shad), splits a long opening block without `༔` into verse and prose, types the
     segments heuristically (`?` = uncertain type, listed on stdout) and **verifies the reconstruction** (segments joined back
     == original). Review the `?` segments and fix types by hand; for texts with prose notation (rol tshig) force
     `--delim shad`.
   - **EPUB**: it is a ZIP — `unzip -o` into the scratchpad, find the XHTML content files (usually under `OEBPS/` or `OPS/`),
     and run `python3 <skill>/scripts/segment_lotsawa_epub.py <content.html> "<text folder>/drafts/source.md"`. Do NOT require
     pandoc (not installed). Lotsawa House EPUBs mark paragraphs with classes
     `tib-verse / pho-verse / eng-verse / tib-note / eng-note / tib / eng / pho-mantra / eng-mantra`; the script pairs them into segments (a `tib-verse` followed by
     `pho-mantra` is a mantra; the colophon starts at the rubric beginning ཅེས་པ་འདི་ཡང་). For other EPUB layouts, adapt inline
     but keep the same source.md format.
   - **md / txt / pasted text**: segment manually into the same format.
2. Classify the content. Tibetan script is the Unicode range U+0F00–U+0FFF. The source may contain Tibetan only, or Tibetan +
   English translation. Keep the source's English-style phonetics as `pho:` lines — they are the pronunciation crib for Step 4;
   translators ignore them.
3. `<text folder>/drafts/source.md` format — one segment = one verse line, one rubric, one mantra, or one heading:

   ```
   ## 12 [verse]
   tib: སེམས་ཅན་དོན་ལ་དགོངས་པའི་དཀོན་མཆོག་གསུམ། །
   pho: semchen dön la gongpé könchok sum
   en: Three Jewels who care for the welfare of beings,

   ## 13 [rubric]
   tib: ལན་བདུན་བརྗོད།
   en: Recite seven times.
   ```

   Types: `[verse]`, `[rubric]`, `[mantra]`, `[heading]`, `[colophon]`. All translators work from this same file; the final text
   is assembled by segment number. Segment types are provisional — as reviewer you may reclassify one during assembly (e.g. a
   Tibetan-only "verse" that is really a mantra); record every reclassification in `drafts/notes.md`.

## Step 2 — Launch the translators in parallel

Announce the delegation in one line first (what is handed off, to which roles, expected wait). Then launch them concurrently.

**Tibetan source — three roles** (model: see config):

| Role | Gets / returns |
|---|---|
| `translator` | `source.md` + `glossary --prompt` + style guide → full draft |
| `reviewer` | `source.md` + draft + glossary → **only the segments it objects to** (fidelity error, broken line correspondence, glossary violation, unidiomatic target phrasing), always with a proposed alternative |
| `terminologist` | `source.md` + the draft(s) + the path to the glossary in effect (it reads the whole `glossary.tsv`, `open` rows included) → `drafts/terminology.md`. Runs **after the drafts land, in parallel with the reviewer.** Four sections: (a) violations of `fixed`/`prov` terms, by segment; (b) **context mismatches** — a glossary term applied where the Tibetan uses the word in another sense (e.g. `rig pa` = rigpa in the glossary, but in the triad སྣང་གྲགས་རིག་པ it is ordinary awareness); (c) Tibetan terms in the text with **no glossary row**, each with a proposed row in the exact TSV format `tib<TAB>wylie<TAB>target<TAB>stem<TAB>status<TAB>note` (status `prov`, note = the justification); (d) one Tibetan term rendered inconsistently within the draft(s). **Never edits the glossary** — the editor merges accepted rows. |
| `pandita` | **On demand, not a batch pass.** Sees only the Tibetan (`source.md`), the segment numbers asked about, the editor's concrete numbered questions, and any reference material the project provides (e.g. a teacher's term list); **never sees or writes the target language.** Returns per question: literal gloss, grammatical analysis (particles, head of the compound, subject and number, honorific), ritual/lineage context, confidence (high/medium/low). When `pandita_tools` lists `dharmamitra`, the prompt names the skill path and the rule: consult it **only when unsure about a specific line or term**, never for whole segments in bulk, log every call with its result in `drafts/pandita.md`, respect the skill's call cap. Output **appended** to `drafts/pandita.md`. |
| `backtranslator` | **only the target-language lines** of a sample → English gloss; you compare it against the Tibetan |

Sample for back-translation: verses longer than the median plus everything the reviewer flagged (~30 segments or 10 % of the
text).

**The cast holds cross-model independence without paying for a second draft.** The reviewer is cheaper and its output directly
actionable; back-translation is the only tool that catches silent meaning loss (where two drafts would err in agreement), which
is why it sees **the target language only**.

**Tibetan + English — four drafts**: `translator` and `translator_2` each produce a `-tib` and an `-en` draft (primary source
language stated in the prompt, the other as cross-check), each with its own session id. In this mode the reviewer role is not
run.

**Tibetan-only source** (no `en:` lines in source.md): do not launch the English roles or a second full draft — the three roles
above suffice, and the prompt omits the sentence about cross-checking against English. Exception: root terms and main sadhanas
(> 300 segments) also get `translator_2`; then review only after both drafts have been compared.

**Texts over ~300 segments**: split them per translator into halves (one ticket per half, `## 1–285` and `## 286–569`), then
merge the drafts and let `compare` verify coverage: `--draft A=drafts/translator-A.md --draft A=drafts/translator-B.md`
(**repeated label, not a comma** — folder names contain commas).

**Review in halves already above ~150 segments.** The reviewer must read source, draft and glossary and verify every numeral, so
it hits limits sooner than the translator and can die leaving no partial file. Write split reviews to `review-A.md` /
`review-B.md` and **tell each half in its prompt that the other is running concurrently** — otherwise they overwrite each
other's file.

**Look for the artifact file before rerunning a dead job**: a run often fails only after the draft or review has been written,
losing nothing but the final report. Name the review file after the role, not the model, and **record the model in `drafts/notes.md`** —
a later revision needs to know whose judgment it is reading.

### Translator prompt/ticket — canonical template

Every translator prompt — the `drafts/prompt-<role>.md` file for `agent` and `copilot`, or a Codex ticket (`<task>` /
`<constraints>` / `<done_when>`) — must contain:

- **Role** — translate into the target language PRIMARILY from the assigned source language, using the other language only as a
  cross-check (state this explicitly; for the Tibetan role add: "where your reading of the Tibetan differs from the English,
  follow the Tibetan"). Add: "This is one of several independent drafts that a reviewer will compare, so translate on your own
  judgment — do not hedge with alternatives."
- **Line correspondence (mandatory)** — every target-language line must correspond to its own Tibetan line; handle enjambment
  line by line; never reorder lines even when the English translation does.
- The path to `drafts/source.md` and the segment count N.
- The **style file in effect (`style.md`) verbatim**, plus the output of `lotsawa.py glossary --prompt` verbatim (the binding
  terminology — never retyped by hand).
- **Segment-type rules**: [verse] one recitable line; [rubric] imperative, 2nd person plural, as defined in the style guide;
  [heading] a short heading; [mantra] do not translate, output a single em-dash; [colophon] translate, but keep a bibliographic
  Wylie citation segment verbatim.
- **Output contract**: write the assigned draft file; for every segment `## <number> [<type>]` + one target-language line; all N
  segments, same numbering as source.md, nothing else in the file. Verification: `grep -c '^## ' <draft>` prints N.
- **Final reply**: one line of confirmation + a numbered list of segments where the reading diverges from the other language or
  the translator was unsure (segment numbers + 3–5 words each). These divergence lists drive Step 3.

The Codex `<done_when>` must include both the style guide having been applied and the grep count.

### Pandita prompt — canonical template

`drafts/prompt-pandita.md` must contain:

- **Role** — you are the pandita, the meaning consultant: you explain what the Tibetan says. You do **not** translate and you
  **never write the target language**; the editor decides the rendering.
- **The Tibetan lines in question, with their segment numbers**, quoted from `drafts/source.md` — nothing else of the text, and
  no target-language line.
- **Numbered questions**, one per contested point: the Tibetan line and what exactly is in doubt.
- **What to return per question**: literal gloss of the line; grammatical analysis (particles, head of the compound, subject and
  number, honorific); ritual/lineage context; confidence `high` / `medium` / `low`.
- Any reference material the project provides (a teacher's term list, when present).
- **When `pandita_tools` lists `dharmamitra`**: the path to the `dharmamitra` skill (sibling directory `skills/dharmamitra`,
  CLI `scripts/dharmamitra.py translate|grammar|search`, hard call cap per text, ethics rules inside its own SKILL.md) and the
  rule — consult it only when unsure about a specific line or term, never for whole segments in bulk, log every call with its
  result, respect the call cap.
- **Output contract**: **append** to `drafts/pandita.md` under a dated round heading (`## <date> — round <n>`), one block per
  question in the order asked. Never overwrite earlier rounds.
- **Final reply**: one line of confirmation.

### Terminologist prompt — canonical template

`drafts/prompt-terminologist.md` must contain:

- **Role** — audit the draft(s) against the glossary in effect; propose, never edit.
- **Inputs**: the path to `drafts/source.md`, the path to each draft, and the path to the **glossary in effect** — read the
  whole `glossary.tsv`, `open` rows included (not the `glossary --prompt` extract).
- **The four output sections**: (a) violations of `fixed` / `prov` terms, by segment; (b) context mismatches — a glossary term
  applied where the Tibetan uses the word in another sense; (c) Tibetan terms in the text with no glossary row; (d) one Tibetan
  term rendered inconsistently within the draft(s).
- **TSV row format** for every proposal in section (c), exactly: `tib<TAB>wylie<TAB>target<TAB>stem<TAB>status<TAB>note` —
  status `prov`, note = the justification.
- **Output contract**: write `drafts/terminology.md`, the four sections in this order, each finding with its segment number.
  **Never edit `glossary.tsv`.**
- **Final reply**: the counts per section (a/b/c/d).

## Step 3 — Compare and iterate

1. **Regenerate `glossary --prompt` immediately before each launch**, not once per batch: Step 5 of the previous text routinely
   changes the glossary, so a stored prompt goes stale within a single text — and the reviewer then reports the stale term as a
   translation defect. `check` reports drift of a text against the glossary in effect; conventions are never copied into
   prompts by hand.
2. Wait for all drafts, then run `compare`. It reports coverage (**a missing segment is fatal**), **Tibetan punctuation
   contamination in target-language lines** with a base recommendation, segments with `ratio < 0.4` for manual review, and
   disputed mantras (one draft gave `—`, the other a translation). Contamination is a real draft defect: **a contaminated draft
   must not be used as the base**. Only then read the translators' divergence lists.
3. Read `drafts/terminology.md` and `drafts/review.md`. Then, **before deciding any contested reading yourself, ask the
   pandita.** Collect the contested segments — the reviewer's fidelity objections, ambiguities the back-translation exposed, the
   terminologist's context mismatches, and your own doubts — into `drafts/prompt-pandita.md` as numbered questions (one Tibetan
   line each, plus what exactly is in doubt) and run the role **once**; a second round only for follow-ups. Record its answers
   and your decision in `drafts/notes.md`.
4. Criteria, in order: fidelity to the Tibetan; line correspondence with the Tibetan (takes precedence over smoother
   reordering); recitability in the target language; terminology consistency across this and previous texts. Where the English
   translation and the Tibetan original diverge, judge case by case which reading is the better translation and which fits the
   text as a whole — neither side wins automatically.
5. On unclear or contested segments, iterate — **question the translator in its own session**, not in a fresh blind run
   (follow-up command in the backend recipes; the session id is in `drafts/notes.md`). Do not settle a hard segment by majority vote
   alone.
6. Record every substantive decision in `drafts/notes.md`: segment number, the candidate renderings, the choice, and why.

## Step 4 — Assemble text.md

1. Choose the base: **the draft with the least contamination** per `compare`. Run
   `build --source drafts/source.md --base drafts/<base>.md -o text.md`.
2. Segments with no phonetics are written to `pho_todo.txt` / `mantra_todo.txt` and `build` exits 2. **Mind the two different
   file formats:** `--pho` takes two fields (`<segment>\t<PHONETICS>`), `--mantra` takes **three**
   (`<segment>\tpho\t<PHONETICS>`). Mantra phonetics put into `pho_done.txt` are ignored and `build` still reports the mantras
   as missing; two fields in `mantra_done.txt` fail on "line does not have 3 fields".
3. Delegate the phonetics in batch to the `phonetics` role, handing it the phonetics file in effect, then rerun `build`
   with `--pho` / `--mantra`. Pass `--pho-lint` when `phonetics_lint: true`. On intake `build` lints the format (UPPERCASE
   unconditionally; the transcription rules only under `--pho-lint`).
4. Manual sub-segmentation (typically a fused opening block that `segment` did not split finely enough) goes into
   `drafts/overrides.json`: `{"1": [["verse", "<tib>", "<translation>"], …]}` — `build` verifies that the override covers the
   whole Tibetan content of the segment and numbers the sub-units `1.1, 1.2…`. **Never renumber segments that already have
   drafts.**
5. Title block and colophon credit go into `drafts/front.txt` / `drafts/back.txt` (`--front` / `--back`); they are copied
   verbatim — editorial text does not belong in the script.
6. After manual edits **always** rerun `check` (with `--original` and `--max-ratio`).
7. Footnotes: sparing — only where the reader needs help (ritual substances, names, genuinely ambiguous lines). Propose them to
   the user rather than multiplying them.
8. Keep `drafts/` (source.md, the drafts, notes.md, todo/done files) next to text.md for later review. Do not scaffold a PDF
   pipeline — text.md only. `drafts/notes.md` holds per-segment decisions, new conventions, uncertain places, **and which
   backend and model produced each file, including the session id** (a fallback substitution belongs here too).
9. An identical Tibetan line may legitimately get a different rendering when its subject carries over from the previous
   segment — never unify such lines mechanically.
10. Present a short report — **only after Step 5**: segments translated, notable divergences, proposed footnotes, open questions
    for the user (including any new phonetics calibration points; feed confirmed ones back into the phonetics file in effect).

## Step 5 — Proofread the target language

The last step before the report. It guards the one thing no previous step guards: **does the finished target language read
naturally.** The reviewer reports only segments it objects to, back-translation measures fidelity alone, `check` and `meter` are
quantitative proxies — nobody has yet enforced the style guide on the result.

1. `lotsawa.py target text.md > drafts/target.txt` — target-language lines only, numbered by `text.md` line numbers. Blank lines
   stay blank: stanza boundaries must be visible, or repetition in adjacent lines cannot be judged.
2. Run **one** agent in the `proofreader` role. It **sees only `drafts/target.txt` — never the original, never the phonetics.**
   With the Tibetan at hand a proofreader excuses a calque by the source, and that is exactly the defect it is there to find.
3. The prompt carries the style file in effect verbatim, including its "Proofreader context" section (false-alarm context and the
   closed set of finding types).
4. Output → `drafts/proofread.md`, one finding per line: `line <N> | <type> | <problem> | <proposal>`. Types are the closed set
   from the style file. No praise, no comments on fidelity, **no edits to `text.md`** — a monolingual reader can "fix" a line by
   throwing away its meaning; the decision stays with the editor.
5. Constraints a proposal must not break: **one line for one line** (line correspondence with the Tibetan is untouchable); the
   phrasing changes, the content does not. When a line looks odd but may carry meaning the proofreader cannot see without the
   original, it uses the `ověř` (verify) type and proposes nothing.
6. The editor goes through the findings: verify each against the Tibetan line in `text.md`, apply or reject, record the decision
   in `drafts/notes.md`. Then rerun `check`.
7. **The pattern goes back into the style file.** A finding that is a class of defect rather than a one-off (it recurs across
   the text, or it is a new kind of error) becomes a new bullet in the style file in effect. Otherwise the next translator makes
   it again — and this is the main payoff of the whole step; the per-text cleanup is a side effect.

## Output format (text.md, interlinear)

text.md is plain text (no markdown markup), one line per element. Target-language wording for the title block, the colophon
credit and the footnote label is **taken from the style guide file**.

- **Title block** — appears twice: once as the cover, then again before the body after a gap of blank lines (the cover page):

  ```
  ༄༅། །<Tibetan title>
  TITLE IN CAPITALS
  Subtitle, if any
  <author line, form per the style guide>

  <ca. 18 blank lines>

  ༄༅། །<Tibetan title>
  Title in sentence case (with subtitle)
  <author line>
  ```

- **Verse** — 3 consecutive lines: Tibetan line, then `<PHONETICS IN UPPERCASE, one syllable = one token>`, then the
  translation. Uppercase phonetics is a **hard format requirement**: the scripts detect phonetic lines by their being
  single-case.
- **Rubric** (instruction) — 2 consecutive lines, no phonetics: Tibetan line, then the translation in the imperative mode the
  style guide prescribes. A rubric with no Tibetan in the source is a single line.
- **Mantra** — **2 consecutive lines**: Tibetan + UPPERCASE phonetics. **No IAST line** (Czech example: `OM BENDZA KILI KILAJA HUNG PHET`).
- **Heading** — a translated line on its own (plus the Tibetan line when the source has one).
- **Colophon** — Tibetan line + translated line, then the translator-credit paragraph (template in the style guide:
  source-language translators, publisher/site, year, bibliographic citation), then the footnote list under the label the style
  guide gives:

  ```
  <Tibetan colophon>
  <translated colophon>

  <translator-credit paragraph>
  <footnote label>
  <footnote text 1>
  <footnote text 2>
  ```

- **Footnotes are marked with roman numerals attached to the word** (`moudrosti,ii`), in reading order; their texts stand at the
  end of the text in the same order, introduced by the same roman numeral. Unicode superscripts (¹ ² ³) are not used.
- Blank line between stanzas and around headings; the lines of one segment stay contiguous (no blank line inside a
  verse/rubric/mantra group).

## Style guide (per language)

The style file in effect (`style.md`) is passed **verbatim** to every translator and to the proofreader. It must contain four
sections: **Style guide** (recitability, line correspondence, Sanskrit and established Buddhist terminology, rubric mode,
proper-name transcription, consistency, output contract, line-length thresholds for `--max-ratio`); **Target-language phrasing**
(the recurring defect classes, with attested example phrases in the target language); **Colophon credit template** (credit
paragraph, footnote-list label, title-block author line); **Proofreader context** (false-alarm context and the closed set of
finding types used in `drafts/proofread.md`). `style.md` in the skill root is the default and the reference implementation; a
project overrides it with its own `style.md`.

## Terminology

The glossary in effect is the **single source** of terminology. Term lists do not belong in SKILL.md — they
freeze on values the glossary has already corrected and get mailed to every translator.

- **One glossary for all texts.** A folder of texts is a batch of work, not a scope of terminology; a per-batch glossary never
  exists. A lineage noted on a term is provenance; its validity is global.
- `fixed` requires an attestation count in `note`, or an explicit justification there.
- With no evidence on either side, the **Tibetan phonetic transcription** wins; Sanskrit only where the target language already
  uses it.
- **New rows come from the terminologist's proposals** in `drafts/terminology.md`, after the editor has accepted them; a `prov`
  term whose context mismatch the terminologist found gets a **context restriction in its `note`**.
- A new or changed term goes into the glossary in effect with a note — not into SKILL.md and not only into `drafts/notes.md`. `drafts/notes.md`
  holds decisions about a segment, the glossary holds the term.
- Phonetics is not terminology — the phonetics file in effect rules there. `check` reports term drift against the glossary, so a
  contradiction does not pass silently.

## Batch mode (a whole folder, dozens of texts)

When the user hands over a whole folder. The batch is a unit of work, not a terminological scope — terminology stays global:

1. **Order: shortest texts first, the largest last.** Conventions and phonetic calibrations established on a short prayer then
   hold for the large sadhana; the other way round the large text is translated blind and has to be revised. The reuse bank
   grows with every finished text, so the largest texts are the cheapest ones by the time their turn comes.
2. Texts that quote another (notation citing incipits of the main sadhana, torma descriptions using its terminology) go
   **after** the text they refer to.
3. **Assembly is serial, delegation is pipelined.** One text = one full run of Steps 1–5 including `check`; do comparison and
   assembly one text at a time, since that is where decisions are made and two half-done comparisons get confused. But pipeline
   the delegations: the translator for text N+1 may run while you review text N. Never launch translators on five texts at once
   — assembly becomes a queue and oversight is lost.
4. Write new or changed terms into the glossary and per-segment decisions into the text's `drafts/notes.md` continuously — not
   at the end, and never into SKILL.md. **Terminologist proposals accumulate across the batch: merge the accepted rows into the
   glossary after each text**, so the next text's `glossary --prompt` already carries them.
5. Realistic pacing: a dozen short-to-medium texts is about a day of work with batched delegations; a hundred or more should be
   planned as batches across several days.

**When the working folder already holds finished `text.md` files**, three optional tools use them:

- `build --reuse <folder>` builds a bank from the sibling finished texts and reuses the phonetics and the translation of
  Tibetan lines that are identical across texts (refrains, mantras, iconography descriptions). **The bank has precedence over
  `--pho` and `--base`**: a correction to a line the bank covers must be made in the sibling text it comes from. `build`
  excludes the output's own folder from the bank; if the `bank` count in the summary nevertheless jumps to the whole segment
  count, the build read this text's previous `text.md` — delete it and rebuild.
- `consist --corpus <folder>` reports the same Tibetan line rendered differently across texts. It is **a report for a human, not
  a gate**: a subject carried over from the previous segment legitimately changes the rendering.
- `glossary --check --corpus <folder>` reports the drift of every text in the folder against the glossary in effect.
