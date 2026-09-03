# Czech style guide

Default style guide of the lotsawa skill (Czech). It is passed verbatim to every
translator and to the proofreader. A same-name `style.md` in the project root overrides
it; another target language writes its own with the same four sections.

## Style guide

- The translation is meant to be recited aloud: it must be faithful to the meaning and
  at the same time sound natural in the target language — rhythm, natural word order,
  no clumsy calques.
- **Line length**: median expansion **2.33×**, p90 3.22×, p99 4.33× (measured on
  published Czech translations; `lotsawa.py meter` reports it, `check --max-ratio` warns).
  A line only becomes a review candidate above **4.3×**.
- **Explanatory insertions in round brackets are desired**, not an exception — 19 % of
  the target-language lines in published Czech translations have them: „(symbolizuje) jedinou
  sféru", „(Coby) sjednocení", „není ani zabíjení ani (rituální) potlačování". They
  supply a subject, a grammatical relation, or a short gloss that would otherwise need
  a footnote.
- Every target-language line corresponds to its own Tibetan line; the order of lines
  never changes, not even when the English translation reordered them.
- Do not translate established Sanskrit terms, only adapt their spelling to the target
  language: bódhičitta, sugata, amrita, dákiní, samádhi, dharmata, mandala, stúpa. Do
  not replace them with native paraphrases.
- Use the established Buddhist terminology of the target language: útočiště, zásluhy,
  věnování, bytosti, říše, zatemnění, soucit, Tři klenoty.
- Write rubrics (instructions) in the imperative, **2nd person plural**: připravte,
  vizualizujte, recitujte, proneste.
- Proper names in Czech transcription: Džigme Lingpa, Rangdžung Dordže, Orgjen Tobgjal
  Rinpočhe, Longčhen Ňingtik, Mipham Rinpočhe, Šákja Šrí, Guru Rinpočhe, Padmasambhava.
- Consistency: one Tibetan term = one settled target-language rendering throughout the
  text.
- Output: numbered segments exactly as in source.md, target language only, one
  translation per segment.

## Target-language phrasing (most frequent source of defects)

- **Do not repeat the same word in two adjacent lines**, even when the Tibetan repeats
  it — reach for a synonym or recast the line. Published Czech translations use synonyms:
  esence / podstata; klam (12×) / zmatení (9×) / iluze (20×). The rule does not apply
  to a refrain, where repetition is plainly intentional. Wrong: „Esencí prázdné
  vědomí… / v tobě, esenci všech útočišť…"; „…bloudí v klamu / kéž se jejich klam
  rozplyne".
- **Material is expressed with a preposition, not an adjective**: „miska z lebky",
  „damaru z lebek", „mála z lebečních kostí" — never „lebeční miska", „lebeční
  damaru". Add a modifier only where the Tibetan carries one (ཐོད = lebka); elsewhere
  the bare term suffices, as in published Czech translations: kapála (27×), damaru (12×).
- **Do not invent words.** „Překážeč" and „od bezpočátku" are not Czech. If you are
  unsure whether a word exists, it does not — paraphrase: „tvůrce překážek", „od času
  bez počátku". The same applies to calques from English.
- **A coined word with no attestation is a defect.** Verify an unfamiliar term against
  the glossary and the finished `text.md` files in the same folder, never by feel; zero
  attestations is a warning, not a licence.
- **An English transcription of a proper name does not belong in the target language —
  and is decided by count, not by feel.** „Dudjom" is the English spelling; published
  Czech translations have **Düdžom 75×** against Dudjom 1×, and „Džigdräl" 15× against
  „Džigdral" 1×. Check every proper name against the attested forms even when you are
  sure; English forms (Dudjom, Tsogyal, Thinley) leak in from bibliographies.
  Exception: a bibliographic citation in the colophon stays verbatim in its original
  English form.
- **Read the line aloud.** The text is recited; whatever cannot be said in one breath,
  or trips the tongue, must be recast.
- **A verse does not open with a cluster of function words.** „se s prudkou touhou…
  klaním", „se ze srdce raduji" — the reflexive „se" belongs after the first strong
  word: „s prudkou touhou a vírou se neustále klaním", „ze srdce se raduji". No verse
  in published Czech translations opens that way, and it trips the tongue in recitation.
- **Replace an imperative that reads as a past tense.** „vyšli sílu soucitu" (from
  vyslat) collapses when read aloud into „vyšli" (from vyjít) — write „projev sílu
  soucitu". Watch for homographs of imperatives generally.
- **Keep the speaker's number from the Tibetan, not from the English.** `bdag` is „já"
  and `bdag la` „mně"; English translations routinely turn this into "we/us" ("grant us
  the four empowerments") and the draft then inherits it. The same trap applies to the
  number of nouns: `lus` = tělo, not „svá těla".
- **Where the English reordered a couplet, verify line correspondence explicitly.** It
  is not only about the order of whole lines: the English translation often pulls the
  final word of the first line onto the second (`gdung shugs kyis`, `sgo gsum gyi`) or
  swaps an invocation with a command. A draft inherits this and neither `compare` nor
  `check` has any grip on it. Give the reviewer this as a separate task in the prompt.
- **`choť` is feminine**: genitive singular „choti", not „chotě" (that is the masculine
  form); instrumental „s chotí". It occurs in every text with `yab yum`.
- **Words from computing and medical Czech do not belong in a practice text.**
  „Vygenerování božstva" (attested: „vytváření", „fáze rozvoje"), „pěti degeneracemi"
  (0 attestations; Czech is „pěti úpadky"). They sound technical and therefore pass
  unnoticed.
- **A title that is typeset twice must be checked twice.** The cover comes from
  `front.txt`, but segment 1 is typeset from the draft; a non-Czech rendering can
  survive in the second occurrence while the cover is fine.
- **Keep one Tibetan term identical throughout the text and settle the variant by
  attested count, not line by line.** The same `klong` has been rendered as both
  prostor and „prostornost" (0 attestations), `kun 'dus` as ztělesnění, sjednocení and
  vtělení (0×), `grub` as realizace and uskutečnění — the attested variant always wins.
  Go over your own terms before you finish the draft.

## Colophon credit template

Translator-credit paragraph, placed after the colophon lines:

```
Do angličtiny přeložili {jména} pro {zdroj}, {rok}. Do češtiny přeloženo
z tibetštiny s přihlédnutím k anglickému překladu, {rok}. Zdroj: {citace}.
```

Footnote-list label: `Poznámky:`

Author line in the title block: `složil {Autor}` / `od {Autora}` (author name in Czech
transcription).

## Proofreader context

Context against false alarms — the proofreader sees only the target-language lines:

- This is a Buddhist practice text; Czechified Sanskrit terms (bódhičitta, dákiní,
  samádhi, dharmata) are correct, not errors.
- Explanatory insertions in round brackets are desired, not a defect.
- Rubrics belong in the imperative, 2nd person plural.
- A verse is not a sentence: a line without a subject or without final punctuation may
  be correct when it continues the adjacent line of the stanza — the defect is only a
  sentence that does not hold together across the whole stanza.
- Skip without comment any line that is not the target language (a leftover
  lower-case phonetics line, a couple per batch).

Closed set of finding types:

- `chybí sloveso` (missing verb)
- `skloňování/shoda` (declension / agreement)
- `vymyšlené slovo` (invented word)
- `kalk` (calque)
- `opakování` (repetition)
- `slovosled` (word order)
- `nevyslovitelné` (unpronounceable)
- `rubrika mimo režim` (rubric in the wrong mode)
- `ověř` (verify — use when unsure, and propose nothing)
