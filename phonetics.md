# Czech phonetic transcription of Tibetan

Default phonetics file of the lotsawa skill (Czech). A same-name `phonetics.md`
in the project root overrides it; another target language writes its own with
the same section structure.

Phonetic lines are written in UPPERCASE; this is a hard requirement of the output
format — the scripts identify phonetic lines by their single case.

Rules for the phonetic line under a Tibetan verse or mantra. Goal: someone
reciting aloud can read it without knowing Tibetan or the English
transliteration conventions.

**The authority is published Czech translations.** The whole system below is
derived from them by measurement, not guessed. Where published translations
disagree with intuition, the published translations win.

## System

| Property | Rule | Evidence in published translations |
|---|---|---|
| Case | **UPPERCASE** | 7719 vs. 3 occurrences |
| Segmentation | **one Tibetan syllable = one token**, except the merged compounds below | token length 2–4 characters |
| Vowel length | **none** — only `Ä Ö Ü` | `É Í Ú Ó` do not occur |
| Apostrophe | kept (`BU'I`, `WO'I`) | 339× |

### Consonants

| Tibetan | transcription | example |
|---|---|---|
| ཅ / ཆ | Č / **ČH** | ČE, ČHOG |
| ཙ / ཚ | TS / **TSH** | TSÄL, TSHOG |
| ཇ, འཇ, བྱ | **DŽ** | DŽE, DŽIN |
| ཞ, གཞ, བཞ | **Ž** | ŽING |
| ཤ, གཤ | **Š** | ŠE |
| ཉ, སྙ, མྱ | **Ň** | ŇI, ŇING |
| ཀྱ / ཁྱ / གྱ | KJ / KHJ / **GJ** | KJE, GJÄL |
| ཁྲ, འཁྲ, ཕྲ, འཕྲ | **THR** or TR (see below) | THRIN LE |
| ཐ, མཐ / ཕ, འཕ / ཁ, མཁ | TH / PH / KH | THUG, PHET, KHA |
| ཡ | **J** | JE, JING |
| ཝ, བ (in position) | W / B | WANG, WA |

`CCH` does not exist — the sibilant is always `TSH`.

### Endings (the most important departure from intuition)

| Tibetan ending | what happens | example |
|---|---|---|
| ག, བ, ལ, མ, ན, ར | **written as is** | THU**G**, DRU**B**, SÖ**L**, DA**M**, KÜ**N**, NO**R** |
| ས | **disappears**, umlauts the vowel | ཐུགས → THUG, ཤེས → ŠE, རུས → RÜ |
| ད | **disappears**, umlauts the vowel | ཐོད → THÖ, ཉིད → ŇI, མེད → ME |

Umlaut: `o → Ö`, `u → Ü`, `e → E`, `i → I`. Evidence in published Czech
translations: ག→G 489×, ལ→L 437×, ད→Ö 247×/E 224×, ས→G 513×/E 398×.

**Note**: a final `-l` umlauts and stays (གསོལ → **SÖL**, 24× in published Czech
translations). An earlier convention of the skill ("final -l does not
umlaut, gsol → sol") was disproved by measurement.

### Ambiguous syllables — one global form

Published translations themselves vary; the skill keeps the first (dominant in
published translations) variant:

| Tibetan | chosen | variant in published translations |
|---|---|---|
| གི, གིས | **GJI** | GI (28× vs. 27× — nearly a tie, in published Czech translations) |
| བར | **BAR** | WAR (18× vs. 16×, in published Czech translations) |
| དཔལ | **PÄL** | PAL (15× vs. 9×, in published Czech translations) |
| ཁྲག | **TRAG** | THRAG (19× vs. 6×, in published Czech translations) |
| འཕྲུལ, འཁྲུལ | **TRÜL** | THRÜL (15× vs. 6×, 10× vs. 7×, in published Czech translations) |
| ཨ | **AH** | A (13× vs. 5×, in published Czech translations) |
| བྱིན | **DŽIN** | ČHIN (14× vs. 3×, in published Czech translations) |

### Merged compounds — exception to "one syllable = one token"

Certain sequences of Tibetan syllables are merged into a single token, rather
than kept as separate tokens, because published translations consistently
merge them — especially proper names and set compounds. A merged compound is
one token:

| Tibetan | merged in published translations | split in published translations |
|---|---|---|
| མཁའ་འགྲོ | **KHANDRO** 465× | KHA DRO 0× |
| ཡེ་ཤེས | **JEŠE** 97× | JE ŠE 6× |
| གུ་རུ | **GURU** 34× | GU RU 1× |
| བླ་མ | **LAMA** 24× | LA MA 7× |
| གསོལ་བ | **SÖLWA** 24× | SÖL WA 1× |
| ཨོ་རྒྱན | **ORGJEN** 25× | O GJEN 0× |
| འོད་ཟེར | **ÖZER** 9× | Ö ZER 3× |
| མཚོ་རྒྱལ | **TSHOGJÄL** 2× | TSHO GJÄL 1× |

(Counts are from published Czech translations.)

Two cases no mechanical syllable test catches: an inserted `n` (KHA + DRO →
KHA**N**DRO) and trisyllabic compounds. Find them from the Tibetan compound,
not from its syllables.

`THÖ THRENG TSÄL` conversely stays **split in verse** (7×) and merges **in a
mantra** (THÖTHRENGTSÄL) — published translations distinguish the two this way.

## Mantras

- **Two lines: Tibetan + phonetics. No IAST line** — published translations
  don't have one.
- Same system as for verses: uppercase, no vowel length.
- `ཧཱུྃ` → **HUNG** always (41× in published Czech translations; a "húng in verse /
  hung in mantra" distinction does not exist in them). `ཕཊ` → **PHET**
  (43×). `བཛྲ` → **BENDZA**. `པདྨ` → **PEMA**.
- Example: `ༀ་བཛྲ་ཀཱི་ལི་ཀཱི་ལ་ཡ་ཧཱུྃ་ཕཊ༔` → `OM BENDZA KILI KILAJA HUNG PHET`

## Proper names in the Czech translation

The translation and colophon use the same system, but capitalized as proper
names: Padmasambhava, Ješe Tsogjäl, Džigme Phüntsok, Dordže Drolö. Sanskrit
deity names stay in Sanskrit with Czech spelling (Vadžrakumára, Amitábha,
Jamarádža).
