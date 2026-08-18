---
name: lotsawa
description: Translate Tibetan Buddhist practice texts (sadhanas, prayers, sur offerings) into Czech via a multi-agent workflow — independent translator, adversarial reviewer and back-translation check (four full drafts when an English translation exists), comparison, and final assembly. Use when the user asks to translate a Tibetan and/or English Buddhist text into Czech. Input is a file (EPUB, md, txt) or pasted text; output is text.md in the interlinear format defined in this skill.
---

# Lotsawa — Tibetan/English → Czech translator

You (the main session) are the reviewer and editor-in-chief. You never translate alone
and never accept a single draft unchecked: a translator produces the draft, an
adversarial reviewer attacks it, a back-translation pass tests a sample for silent
meaning loss, and you decide every contested segment and assemble the final text.
Where an English translation exists, four full drafts replace the reviewer (see below).

This skill is self-contained: every format and terminology rule it needs is defined
below. Do not depend on other files in the working folder existing — previously
translated texts, when present, only add to the rules here, never replace them.

Mechanické kroky (segmentace, porovnání draftů, montáž, lint) dělá
`scripts/lotsawa.py` — **nikdy je nepiš inline v pythonu.** Celý běh jednoho textu:

```
python3 <skill>/scripts/lotsawa.py segment original.md -o drafts/source.md
# → 2 (nebo 4) drafty od překladatelů, viz Step 2
python3 <skill>/scripts/lotsawa.py compare --source drafts/source.md \
        --draft G=drafts/gemini-tib.md --draft C=drafts/codex-tib.md -o drafts/review.md
python3 <skill>/scripts/lotsawa.py pho --source drafts/source.md -o drafts/pho_done.txt
#   → fonetika se SKLÁDÁ Z LEXIKONU vzorových textů (~60 % veršů); zbytek jde do
#     pho_todo.txt s ??? a doplní se podle pravidel v phonetics.md
python3 <skill>/scripts/lotsawa.py build --source drafts/source.md \
        --base drafts/<základ>.md --reuse ../ \
        --reuse-bank /Users/prokop/texts/reference/mined/triplet_bank.tsv \
        --pho drafts/pho_done.txt -o text.md
# → ruční editace (titulní blok, poznámky, reklasifikace)
python3 <skill>/scripts/lotsawa.py check text.md --original original.md
```

Kontroly, které nepatří k jednomu textu, ale k celému cyklu:

```
python3 <skill>/scripts/lotsawa.py cz '<český výraz>' [--pho]     # doklad ve vzorech
python3 <skill>/scripts/lotsawa.py glossary --audit               # opora glosáře
python3 <skill>/scripts/lotsawa.py consist --corpus '<složka>'    # konzistence textů
```

- **`cz` nahrazuje ruční `grep -ho -i`** a existuje kvůli dvěma pastem, které v cyklu
  Pudri Rekpung reálně způsobily chybu: podřetězec (`grep trvalost` najde
  „vytrvalost", a přesně tak se do glosáře dostal nedoložený tvar) a velikost písmen.
  Rozlišuje celé slovo / předponu / podřetězec a sám hlásí, když jsou doklady jen
  uvnitř jiných slov. `--pho` počítá jen na fonetických řádcích a předponu neposuzuje
  (fonetické tokeny se neskloňují: `THRI` by jinak „doložilo" `THRIN` z phrin las).
- **`glossary --audit` je opačný směr než `--check`**: `--check` hlídá text proti
  glosáři, `--audit` glosář proti vzorům. Hlásí `fixed` termíny, jejichž stem nemá
  ve vzorech doklad. Pouštěj ho **před** cyklem, ne po něm — šest vad glosáře
  (Džigdral, vidjádhara, vítězové, samaji a dva neinvariantní stemy) prošlo celým
  prvním během Pudri Rekpung právě proto, že tuhle kontrolu nikdo neudělal.
- **`consist`** hlídá, že týž tibetský řádek dostal napříč hotovými texty tutéž
  češtinu. Banka tripletů to zajišťuje jen při buildu, takže text sestavený dřív,
  než sourozenec existoval, o ní neví. **Nahlášený rozpor není automaticky vada:**
  podmět může přicházet z předchozího segmentu, takže identický tibetský řádek
  legitimně dostane jinou shodu. V ohňové oběti je `རང་གཞན་འཁོར་བཅས་ལ་ཐིམ་པས` 3× a má
  „vplyne" tam, kde je podmětem singulární „esence požehnání", a „vplynou" v refrénech,
  kde jsou podmětem „paprsky". `consist` je report pro člověka, ne gate — každý
  rozpor přečti a rozhodni, nesjednocuj ho mechanicky.

Pravidlo skriptu: **ztráta nebo poškození dat je fatální (exit 1), redakční soud je
varování.** Exit 2 znamená „chybí fonetika" — není to chyba, `*_todo.txt` jsou
zapsané. `check` pouštěj i po každé ruční editaci; právě tam vady dřív unikaly.
`selftest` po každé úpravě skriptu.

## Two source shapes

| Zdroj | Obsazení | Kdy |
|---|---|---|
| **Jen tibetština** (wiki, `original.md` jako jeden dlouhý řádek) | překladatel + recenzent + zpětný překlad (viz Step 2) | Výchozí případ. Tsadra/Dudjom Wiki nemá anglické překlady. |
| **Tibetština + angličtina** (EPUB Lotsawa House) | 4 drafty: `gemini-tib`, `gemini-en`, `codex-tib`, `codex-en` | Když zdroj nese anglický překlad — dva zdrojové jazyky dávají skutečnou perspektivní různost. |

**Proč u tibetských zdrojů nejsou dva plné drafty výchozí:** dva modely na identickém
zadání se rozcházejí většinou jen stylisticky, zatímco těžká místa (technická rituální
terminologie) označí za nejistá **shodně** — a to je selhání, které porovnání draftů
principiálně nezachytí. Redundanci proto nahrazuje různost rolí; dva plné drafty se
platí jen tam, kde se nezávislé čtení vyplácí (kořenové termy, hlavní sádhany,
> 300 segmentů).

## Step 1 — Prepare the source

1. Load the input:
   - **Tibetan-only `original.md`** (nejčastější): `lotsawa.py segment original.md -o
     drafts/source.md`. Skript vybere dělítko (`༔` ≥ 2× → terma režim, jinak shad),
     rozseká dlouhý úvodní blok bez `༔` na verše a prózu, otypuje segmenty
     heuristicky (`?` = nejistý typ, vypíše seznam) a **povinně ověří rekonstrukci**
     (segmenty spojené zpět == originál). Přehlédni `?` segmenty a typy uprav ručně;
     u textů s prozaickou notací (rol tshig) vynuť `--delim shad`.
   - **EPUB**: it is a ZIP — `unzip -o` into the scratchpad, find the XHTML content
     files (usually under `OEBPS/` or `OPS/`), and run
     `python3 <skill dir>/scripts/segment_lotsawa_epub.py <content.html> "<text folder>/drafts/source.md"`.
     Do NOT require pandoc (not installed). Lotsawa House EPUBs mark paragraphs with
     classes `tib-verse / pho-verse / eng-verse / tib-note / eng-note / tib / eng /
     pho-mantra / eng-mantra`; the script pairs them into segments (a `tib-verse`
     followed by `pho-mantra` is a mantra; the colophon starts at the rubric beginning
     ཅེས་པ་འདི་ཡང་). For other EPUB layouts, adapt inline but keep the same
     source.md format.
   - **md / txt / pasted text**: segment manually into the same format.
2. Classify the content. Tibetan script is the Unicode range U+0F00–U+0FFF. The source
   may contain Tibetan only, or Tibetan + English translation. Keep the source's
   English-style phonetics as `pho:` lines — they are the pronunciation crib for
   Step 4; translators ignore them.
3. `<text folder>/drafts/source.md` format — one segment = one verse line, one rubric,
   one mantra, or one heading:

   ```
   ## 12 [verse]
   tib: སེམས་ཅན་དོན་ལ་དགོངས་པའི་དཀོན་མཆོག་གསུམ། །
   pho: semchen dön la gongpé könchok sum
   en: Three Jewels who care for the welfare of beings,

   ## 13 [rubric]
   tib: ལན་བདུན་བརྗོད།
   en: Recite seven times.
   ```

   Types: `[verse]`, `[rubric]`, `[mantra]`, `[heading]`, `[colophon]`. All four
   translators work from this same file; the final text is assembled by segment
   number. Segment types are provisional — as reviewer you may reclassify one during
   assembly (e.g. a Tibetan-only "verse" like guru pema siddhi hung that is really a
   mantra); record every reclassification in notes.md.

## Step 2 — Launch the translators in parallel

Announce the delegation in one line first (what is handed off, to which models,
expected wait). Then launch them concurrently — dva u tibetského zdroje, čtyři když
je po ruce angličtina:

**Tibetský zdroj — tři role:**

| Soubor | Role | Model | Co dostane / co vrací |
|---|---|---|---|
| `drafts/gemini-tib.md` | Překladatel | `gemini-3.1-pro-preview` přes **copilot CLI** (příkaz níže); při výpadku Opus subagent | `source.md` + glosář (`glossary --prompt`) → plný draft |
| `drafts/review-codex.md` | Adversariální recenzent | `gpt-5.6-sol` přes **Codex** (`/sous-chef:fire`, jeden ticket) | `source.md` + draft + glosář → **jen segmenty, kde namítá** (chyba věrnosti, porušená řádková korespondence, porušený glosář, nečeská formulace), vždy s návrhem alternativy |
| `drafts/backtrans.md` | Zpětný překlad | Sonnet/Haiku (Agent tool) | **jen české řádky** vzorku segmentů → anglický gloss; recenzent-šéf ho porovná s tibetštinou |

Soubor recenze pojmenuj podle modelu, který ji psal — `review-codex.md`, `review-opus.md`.
Pozdější revize potřebuje vědět, čí soud čte; `review-codex.md` napsané jiným modelem je past.

**Obsazení drží cross-model nezávislost bez placení druhým draftem.** Čtyři různé
modely v řadě: Gemini překládá, GPT recenzuje, Sonnet zpětně překládá, Opus koriguje
(Step 5). Dřív překládal i recenzoval Fable a nezávislost visela jen na zpětném
překladu a korektuře — to už neplatí a je to hlavní důvod téhle sestavy.

**Když recenzent nemůže běžet.** Codex spotřebuje na text 170–240 k tokenů a při
vyčerpané kvótě běhy padají — dvakrát v cyklu Pudri Rekpung, vždy až po dopsání
`review-codex.md`, takže artefakt přežil a ztratila se jen závěrečná zpráva
(**podívej se po souboru, než recenzi pustíš znovu**). Náhrada je **Opus subagent**
(Agent tool, `model: opus`) v téže roli, výstup do `review-opus.md`; ztrácí se cross-model
kontrola proti Gemini draftu, ne nezávislost modelu. U kořenových termů a hlavních
sádhan se na Codexe počkej, místo aby ses ho vzdal.

Kanonické spuštění překladatele — **z kořene repa**, `run_in_background: true`, prompt
v souboru (glosář + Style guide se do `-p` argumentu neobalují):

```bash
cd /Users/prokop/texts
SID=$(uuidgen)                    # zapiš do drafts/notes.md — umožní doptání (Step 3.5)
copilot -p "Přečti '<text>/drafts/prompt-gemini-tib.md' a splň zadání přesně podle něj." \
  --model gemini-3.1-pro-preview --effort high \
  --allow-all-tools --no-color -s --log-level none \
  --session-id "$SID" > '<text>/drafts/gemini-tib.job.log' 2>&1
```

- `--allow-all-tools` je **povinný** — bez něj non-interactive režim vůbec neběží
  (ekvivalent `COPILOT_ALLOW_ALL=true`). Bez něj by copilot draft nezapsal.
- `high` je u tohohle modelu **maximum**: `--effort` nabízí až `max`, ale
  gemini-3.1-pro-preview přijímá jen `none / low / medium / high` a na `xhigh` i `max`
  padá hned (`Reasoning effort "xhigh" is not supported for model …`) — změřeno.
  Codex naproti tomu jede `xhigh`; ta asymetrie je vlastnost modelů, ne opomenutí.
- Celý prompt podle šablony níže (role, řádková korespondence, Style guide verbatim,
  `glossary --prompt`, kontrakt výstupu) napiš do `drafts/prompt-gemini-tib.md`; `-p`
  je jen ukazatel na něj. Dlouhý prompt v argumentu je zbytečná past na quoting.
- Spouštěj z kořene repa, ne z podsložky textu (týž důvod jako u Codexe níže).
- Nikdy nepolluj; `run_in_background` ohlásí konec sám. Fallback wakeup 1200 s+ zůstává.
- Dlouhé texty: `--max-ai-credits <N>` je soft cap na kredity session.
- V copilotu je zapnutý plugin ponytail („lazy dev" persona). Ve smoke testu do
  odpovědi nic neinjektoval; kdyby prosákl, doplň do promptu větu, že na překlad
  neplatí.
- Copilot **nepotřebuje git** (na rozdíl od `fire`) a `/Users/prokop` je v jeho
  `trustedFolders`. Ověřeno smoke testem — po updatu CLI ho zopakuj:
  `copilot -p "Odpověz přesně: LOTSAWA OK" --model gemini-3.1-pro-preview --allow-all-tools -s --no-color`

Recenzent je levnější než druhý plný draft a jeho výstup je přímo akcionovatelný.
Zpětný překlad je jediný nástroj, který chytá tichou ztrátu významu (kde by se dva
drafty mýlily souhlasně) — proto vidí **výhradně** češtinu. Vzorek: verše, které
nepřišly z banky tripletů, delší než medián, plus vše, co označil recenzent
(~30 segmentů nebo 10 % textu).

**Tibetština + angličtina — čtyři drafty:**

| Draft file | Translator | Source language | How to launch |
|---|---|---|---|
| `drafts/gemini-en.md` | Gemini (copilot CLI) | English (Tibetan as reference) | příkaz výše, vlastní `--session-id` |
| `drafts/gemini-tib.md` | Gemini (copilot CLI) | Tibetan (English as reference) | příkaz výše, vlastní `--session-id` |
| `drafts/codex-en.md` | Codex | English (Tibetan as reference) | `/sous-chef:fire`, one ticket |
| `drafts/codex-tib.md` | Codex | Tibetan (English as reference) | `/sous-chef:fire`, one ticket |

V tomhle režimu Codex překládá a recenzentská role se nespouští. Keep the draft
filenames (`gemini-*`) even when Opus stands in for the copilot run, so the comparison
step and notes stay comparable across texts; record the substitution in `drafts/notes.md`.

**Tibetan-only source** (no `en:` lines in source.md): nespouštěj anglické role ani
druhý plný draft — jde se třemi rolemi z tabulky výše a v promptu vynech větu
o cross-checku s angličtinou. Výjimka: kořenové termy a hlavní sádhany (> 300
segmentů) dostanou navíc druhý plný draft (`codex-tib.md`); pak recenzuj až po
porovnání obou draftů.

Codex runs via `/sous-chef:fire` — one ticket per draft (or per review), background
jobs. Model neuváděj v ticketu: `fire` ho nechává propadnout do `~/.codex/config.toml`,
kde je `gpt-5.6-sol` + `xhigh`. Do NOT use `/sous-chef:serve`: its taste/refire stages
duplicate what the comparison in Step 3 already does. This repo is not a git repository,
so add `--skip-git-repo-check` to the codex invocation; the tickets only create one new
file each, so no git baseline is needed. Never poll the jobs; completion notifies you.
After launching every delegation, arm one fallback wakeup (1200 s+) in case a job
hangs, and cancel it once all drafts have landed.

**Codex fire vždy z kořene repa** (`cd /Users/prokop/texts`) — sandbox
`workspace-write` je vázaný na cwd, takže spuštění z podsložky textu zápis do jiné
složky odmítne („cílový adresář je mimo zapisovatelný workspace") a celý run se
zahodí. Přihodilo se to jednou; ticket byl v pořádku, jen cwd ne.

**Texty nad ~300 segmentů** rozděl každému překladateli na poloviny (jeden ticket na
polovinu, `## 1–285` a `## 286–569`), pak drafty slij a nech `compare` ověřit
pokrytí: `--draft G=gemini-A.md --draft G=gemini-B.md` (opakovaný label, ne čárka —
názvy složek obsahují čárky).

**Recenzi dělej po polovinách už nad ~150 segmenty.** Recenzent musí přečíst zdroj,
draft, glosář a u manuálů ověřit každou číslovku, takže spadne dřív než překladatel:
recenze 167segmentového rituálu ohňové oběti umřela na `Request timed out` a
nezanechala ani částečný soubor. Dělené recenze piš do `review-<model>-A.md` a
`review-<model>-B.md` a **v promptu každé polovině řekni, že druhá běží současně** —
jinak si soubor toho druhého přepíšou.

### Translator prompt/ticket — canonical template

Every translator prompt — copilot (`drafts/prompt-*.md`), Agent tool, or Codex ticket
(`<task>`/`<constraints>`/`<done_when>`) — must contain:

- **Role** — translate into Czech PRIMARILY from the assigned source language, using
  the other language only as a cross-check (state this explicitly; for the Tibetan
  role add: "where your reading of the Tibetan differs from the English, follow the
  Tibetan"). Add: "This is one of several independent drafts that a reviewer will
  compare, so translate on your own judgment — do not hedge with alternatives."
- **Line correspondence (mandatory, the key lesson of run 1)** — every Czech line
  must correspond to its own Tibetan line; handle enjambment line by line; never
  reorder lines even when the English translation does.
- The path to `drafts/source.md` and the segment count N.
- The complete **Style guide** section below, verbatim, plus the output of
  `lotsawa.py glossary --prompt` (the binding terminology — never retyped by hand).
- **Segment-type rules**: [verse] one recitable Czech line; [rubric] imperative 2nd
  person singular; [heading] short Czech heading; [mantra] do not translate, output
  a single em-dash; [colophon] translate, but keep a bibliographic Wylie citation
  segment verbatim.
- **Output contract**: write the assigned draft file; for every segment
  `## <number> [<type>]` + one Czech line; all N segments, same numbering as
  source.md, nothing else in the file. Verification (Codex `<done_when>`):
  `grep -c '^## ' <draft>` prints N.
- **Final reply (all translators)**: one line of confirmation + a numbered list of
  segments where their reading diverges from the other language or they were unsure
  (segment numbers + 3–5 words each). These divergence lists drive Step 3.

## Step 3 — Compare and iterate

0. **Každý sporný termín nejdřív protáhni konkordancí, teprve pak ho označ za
   nejistý.** V repu leží ~196 tibetských originálů téže linie; termín neprůhledný
   v jednom textu bývá jinde v jasnějším kontextu:
   `lotsawa.py concord 'ཐོར་ཐུན'` prohledá originály **i hotové překlady** (u nich
   vypíše, jak už termín byl přeložen). Ověřeno: u `ཐོར་ཐུན` dal Troma Nagmo vazbu
   na ranní seanci, která vyvrátila dohad „závěrečná seance"; u `དཔལ་གཏོར` popis
   tvaru z Khandro Thuktik. Do `notes.md` piš rozhodnutí s odkazem na nalezený
   kontext; „nejisté" je až to, co konkordance neuzavře.

   **Sporná česká formulace se ověřuje stejně, jen z druhé strany** — `concord` hledá
   podle tibetštiny, ale ptát se je potřeba i „jak tohle vzory česky říkají":

   ```
   python3 <skill>/scripts/lotsawa.py cz '<český výraz>'
   ```

   **Nepiš si ten grep ručně.** `grep -ho -i '[^.]*X[^.]*'` má dvě pasti a obě
   v tomto cyklu reálně způsobily chybu: `grep trvalost` najde i „vytrvalost" (takhle
   se do glosáře dostal tvar s nula doklady) a `grep` bez `-i` mine malé písmeno
   uvnitř složeniny („kílaj" v „Vadžrakílaji"). `cz` rozlišuje celé slovo, předponu
   a podřetězec a sám hlásí, když jsou doklady jen uvnitř jiných slov.

   Rozhoduje počet výskytů, ne dojem. Nula výskytů u termínu, který zní jako čeština,
   znamená, že ho někdo vymyslel — přesně tak se do glosáře dostal „překážeč" (0×
   ve vzorech, správně „tvůrci překážek", 11×) a rozeslal se všem překladatelům.
   Než termín zapíšeš do `glossary.tsv` jako `fixed`, musí mít doložený počet v note
   **a projít `glossary --audit`**.

   Pozor na jedno: `glossary --check --file X` znamená „použij X jako glosář", ne
   „zkontroluj text X". `--corpus` bere texty v jakékoli hloubce, takže
   `--corpus /Users/prokop/texts` je audit celého repa.
1. Terminologie: `lotsawa.py glossary --prompt` vygeneruje závaznou sekci do promptů.
   **Generuj ji znovu bezprostředně před každým spuštěním překladatele**, ne jednou za
   cyklus. Step 5 předchozího textu glosář rutinně mění (korektura ho v Pudri Rekpung
   opravila u čtyř termínů), takže uložený prompt zastará během jednoho textu: text 5
   překládal podle souboru, v němž ještě stálo `vítězové` a `samaji`, a recenzent to
   pak nahlásil jako vadu překladu, i když to byla vada mého procesu.
   `--check` ohlásí drift proti `glossary.tsv`. Konvence se do promptů nekopírují
   ručně a **nemají cyklovou variantu** — glosář je jeden. Kromě toho projdi
   `*/drafts/notes.md` hotových textů — rozhodnutí po segmentech tam vážou i tento
   text.
2. Wait for all drafts, pak `lotsawa.py compare`. Vypíše pokrytí (chybějící segment
   = fatální), **kontaminaci tibetskou interpunkcí v českých řádcích** s doporučením
   základu, segmenty s `ratio < 0.4` k ruční revizi a sporné mantry (jeden draft dal
   `—`, druhý překlad). Kontaminace je reálná vada draftu: v jednom textu měl jeden
   překladatel vlepenou tibetskou interpunkci v 57 z 63 segmentů — takový draft se
   nesmí použít jako základ. Až pak čti divergenční seznamy od překladatelů.
3. Criteria, in order: fidelity to the Tibetan; line correspondence with the Tibetan
   (takes precedence over smoother reordering); recitability in Czech; terminology
   consistency across this text and previous texts.
4. When the English translation and the Tibetan original diverge, judge which reading
   is the better translation and which fits the text as a whole — neither side wins
   automatically.
5. On unclear or contested segments, iterate — překladatele se doptej v jeho vlastní
   session, ne novým během naslepo:
   `copilot --session-id "$SID" -p '<cílená otázka>' --allow-all-tools -s --no-color`
   (`-r "$SID"` je totéž; `$SID` je v `notes.md` ze Step 2). Pro Codex krátký
   follow-up `/sous-chef:fire`. Do not settle a hard segment by majority vote alone.
6. Record every substantive decision in `drafts/notes.md`: segment number, the
   candidate renderings, the choice, and why.

## Step 4 — Assemble text.md

1. Zvol základ (draft s nejmenší kontaminací dle `compare`) a spusť `lotsawa.py
   build --source … --base … --reuse ../`. **Před opakovaným buildem odkliď
   `text.md` toho textu, který staví.** `--reuse ../` globuje `*/text.md` včetně
   vlastní složky, takže druhý build čte svůj vlastní předchozí výstup, a banka má
   přednost před `--pho` i `--base` — oprava fonetiky nebo základu se pak tiše
   zahodí a `text.md` zůstane na staré hodnotě. Poznávací znak: `bank` v souhrnu
   vyskočí z jednotek na počet segmentů textu (`bank 1` → `bank 62`). `--reuse` staví **banku tripletů** ze
   sourozeneckých `text.md` v cyklu: identické tibetské řádky (ikonografie,
   rozpuštění, refrény, mantry) přeberou hotovou fonetiku i češtinu. Výtěžnost
   v cyklu Pudri Rekpung: 105 z 569 segmentů u hlavní sádhany, 40 u kořenové termy,
   26 u zmocnění — banka narostla na ~980 tripletů, takže pozdější texty jsou
   výrazně levnější.
2. Segmenty, které banka nepokryla, vypíše `build` do `pho_todo.txt` /
   `mantra_todo.txt` a skončí s exit 2. **Pozor na formát dvou různých souborů:**
   `--pho` bere dvě pole (`<segment>\t<FONETIKA>`), ale `--mantra` bere **tři**
   (`<segment>\tpho\t<FONETIKA>`) — `load_tsv(cols=2)` staví vnořený slovník a
   `build` z něj čte klíč `pho`. Mantrová fonetika vložená do `pho_done.txt`
   se ignoruje a `build` mantry nahlásí jako chybějící; dvě pole v
   `mantra_done.txt` skončí na „řádek nemá 3 polí". Fonetiku deleguj dávkově podle pravidel
   v [phonetics.md](phonetics.md), pak `build` spusť znovu s `--pho`/`--mantra`.
   **Slévání složenin už neděleguj** — `pho` si bigramový test dělá sám proti
   fonetickým řádkům vzorů a slitá místa vypíše (`sloučeno dle vzorů: N×`). Je to
   čisté počítání; subagent na tom spotřeboval ~150 k tokenů na text. Agentovi
   zůstává doplnění neznámých slabik a sanskrt v mantrách. Co test principiálně
   nechytá a nepředstírá to: vsunuté `n` (KHA + DRO → KHA**N**DRO) a trojslabičné
   složeniny — ty hledej podle tibetské složeniny. Při příjmu `build` lintuje konvenci vzorů
   (VERZÁLKY, bez délek, `PHET` ne `PHE`, `TSH` ne `CCH` — viz `phonetics.md`) a nové
   fonetické tokeny proti korpusu (`WARN: DIKČHEN (nové) vs DIKČEN (14×)`).
3. Ruční rozklad segmentu na podjednotky (typicky slitý úvodní blok, když ho
   `segment` neroztrhal podle potřeby) patří do `drafts/overrides.json`:
   `{"1": [["verse", "<tib>", "<čeština>"], …]}` — `build` ověří, že override pokrývá
   celý tibetský obsah segmentu, a podjednotky číslo `1.1, 1.2…`. Nikdy nepřečísluj
   segmenty, které už mají drafty.
4. Titulní blok a kolofonní kredit dej do `drafts/front.txt` / `back.txt`
   (`--front`/`--back`), kopírují se verbatim — editorial nepatří do skriptu.
5. Po ručních editacích **vždy** `lotsawa.py check text.md --original original.md`.
6. Footnotes: sparing — only where the reader needs help (ritual substances, names,
   genuinely ambiguous lines). Inline Unicode superscripts (¹ ² ³), texts listed at
   the end under `Poznámky:`. Propose them to the user rather than multiplying them.
7. Keep `drafts/` (source.md, the drafts, notes.md, todo/done soubory) next to
   text.md for later review. Do not scaffold the PDF pipeline (fonts, build_tex.py) —
   text.md only.
8. `drafts/notes.md`: rozhodnutí po segmentech, nová konvence, nejistá místa **a
   který model draft pořídil, včetně copilot `--session-id`** (když Opus zaskakoval za
   copilota, patří to do poznámek — jinak se pozdější revize nedozví, čí soud
   srovnávala, a bez session ID se nedá doptat).
9. Present a short report — **až po Step 5**: segments translated, notable
   divergences, proposed footnotes, open questions for the user (including any new
   phonetics calibration points — feed confirmed ones back into phonetics.md and new
   conventions into the Established conventions list below).

## Step 5 — Korektura češtiny

Poslední krok před reportem. Hlídá to jediné, co žádný předchozí krok nehlídá:
**zní hotová čeština česky.** Codex recenzent nečeskou formulaci nahlásit smí, ale
hlásí jen segmenty, kde má námitku; zpětný překlad měří výhradně věrnost; `check`
a `meter` jsou kvantitativní proxy (expanze slabik, osiřelé řádky). Style guide
níže tedy do téhle chvíle nikdo na výsledku nevymáhá.

1. `lotsawa.py czech text.md > drafts/czech.txt` — jen české řádky, očíslované
   čísly řádků `text.md`. Prázdné řádky zůstávají prázdné: hranice strof musí být
   vidět, jinak nelze soudit opakování v sousedních řádcích.
2. Spusť **jednoho** agenta (Agent tool, model **Opus**). Role: korektor českého
   jazyka, redaktor textů určených k hlasité recitaci. **Vidí výhradně
   `drafts/czech.txt` — nikdy originál, nikdy fonetiku.** S tibetštinou po ruce si
   kalk omluví zdrojem („ale tibetsky to tak stojí"), a to je přesně vada, kterou
   má najít; ze stejného důvodu vidí zpětný překlad jen češtinu.
3. Prompt nese verbatim Style guide i celou sekci „Česká formulace" (níže) a tento
   kontext proti falešným poplachům:
   - buddhistický praxový text; počeštěné sanskrtské termíny (bódhičitta, dákiní,
     samádhi, dharmata) jsou správné, ne chyba,
   - vysvětlující vsuvky v kruhových závorkách jsou žádoucí, ne vada (19 % řádků
     vzorů),
   - rubriky patří do 2. osoby množného čísla imperativu,
   - verš není věta: řádek bez podmětu nebo bez koncové interpunkce může být
     správný, když navazuje na sousední řádek strofy — vada je až věta, která
     nedrží pohromadě ani přes celou strofu,
   - řádek, který není čeština (zbytek fonetiky minuskami, řádově dva na cyklus),
     přeskoč bez komentáře,
   - neznámé slovo se ověřuje ve vzorech, ne odhadem:
     `grep -ho -i '[^.]*<výraz>[^.]*' /Users/prokop/texts/reference/mined/*.txt | head`
     — nula výskytů je varovný signál, ne povolení.
4. Výstup → `drafts/korektura.md`, jeden finding na řádek:
   `ř.<N> | <typ> | <problém> | <návrh>`. Typy jsou uzavřená množina: `chybí
   sloveso`, `skloňování/shoda`, `vymyšlené slovo`, `kalk`, `opakování`,
   `slovosled`, `nevyslovitelné`, `rubrika mimo režim`, `ověř`. Žádná pochvala,
   žádný komentář k věrnosti, **žádná editace `text.md`** — monolingvální čtenář
   může „opravit" tak, že zahodí význam; rozhodnutí zůstává u redaktora.
5. Vazby, které návrh nesmí porušit: **jeden řádek za jeden řádek** (řádková
   korespondence s tibetštinou je nedotknutelná), mění se formulace, ne obsah.
   Když řádek vypadá divně, ale může nést význam, který korektor bez originálu
   nevidí, použije typ `ověř` a nenavrhuje nic.
6. Redaktor projde findingy: každý návrh ověří proti tibetskému řádku v `text.md`,
   aplikuje nebo zamítne, rozhodnutí zapíše do `drafts/notes.md`. Pak **znovu**
   `lotsawa.py check text.md --original original.md`.
7. **Vzorec zpátky do skillu.** Finding, který je třída vady, ne jednotlivost
   (opakuje se napříč textem, nebo je to nový druh chyby), patří jako nová odrážka
   do sekce „Česká formulace". Jinak ho příští překladatel udělá znovu — a tohle je
   hlavní přínos celého kroku, per-text úklid je vedlejší.

## Output format (text.md, interlinear)

text.md is plain text (no markdown markup), one line per element:

- **Title block** — appears twice: once as the cover, then again before the body
  after a gap of blank lines (the cover page):

  ```
  ༄༅། །<tibetský titul>
  ČESKÝ TITUL VELKÝMI PÍSMENY
  Podtitul, pokud existuje
  složil {Autor} / od {Autora}          <- author in Czech transcription

  <cca 18 prázdných řádků>

  ༄༅། །<tibetský titul>
  Český titul větnou sazbou (s podtitulem)
  složil {Autor} / od {Autora}
  ```

- **Verse** — 3 consecutive lines:

  ```
  <tibetský řádek>
  <FONETIKA VERZÁLKAMI, jedna slabika = jeden token>
  <český překlad>
  ```

- **Rubric** (instruction) — 2 consecutive lines, no phonetics (typeset italic in
  the PDF): Tibetan line, Czech line v 2. osobě množného čísla. A rubric with no Tibetan in the source is a
  single Czech line.
- **Mantra** — **2 consecutive lines**: Tibetan + fonetika VERZÁLKAMI. Žádný řádek
  IAST — vzorové texty jej neobsahují (`OM BENDZA KILI KILAJA HUNG PHET`).
- **Heading** — a Czech line on its own (plus the Tibetan line when the source has
  one).
- **Colophon** — Tibetan line + Czech line, then a translator-credit paragraph in
  Czech naming the source-language translators, publisher/site, year, and the
  bibliographic citation, then the footnote list:

  ```
  <tibetský kolofon>
  <český kolofon>

  Do angličtiny přeložili {jména} pro {zdroj}, {rok}. Do češtiny přeloženo
  z tibetštiny s přihlédnutím k anglickému překladu, {rok}. Zdroj: {citace}.
  Poznámky:
  <text poznámky 1>
  <text poznámky 2>
  ```

- **Poznámky se značí římskými číslicemi přilepenými ke slovu** (`moudrosti,ii`),
  v pořadí čtení; jejich texty stojí na konci textu ve stejném pořadí, uvozené touž
  římskou číslicí. (Vzory: ~293 markerů; Unicode indexy ¹ ² ³ se nepoužívají.)
- Blank line between stanzas and around headings; lines of one segment stay
  contiguous (no blank line inside a verse/rubric/mantra triplet).

## Style guide (pass verbatim to every translator)

- Přeložený text je určen k hlasité recitaci: překlad musí být věrný významu a
  zároveň znít přirozeně česky — rytmus, přirozený slovosled, žádné kostrbaté kalky.
- **Délka řádku**: naměřeno na 1683 verších vzorových textů — medián expanze
  **2,33×**, p90 3,22×, p99 4,33×. Kandidát revize je až řádek nad **4,3×**. Měří
  `lotsawa.py meter text.md`; `check` na to varuje.
- **Vysvětlující vsuvky v kruhových závorkách jsou žádoucí**, ne výjimka — vzory je
  mají v 19 % českých řádků: „(symbolizuje) jedinou sféru", „(Coby) sjednocení",
  „není ani zabíjení ani (rituální) potlačování". Doplňují podmět, gramatický vztah
  nebo krátký výklad, který by jinak musel do poznámky.
- Každý český řádek odpovídá svému tibetskému řádku; pořadí řádků se nemění, ani
  když je angličtina přeskládala.
- Zavedené sanskrtské termíny nepřekládej, jen počešti pravopis: bódhičitta, sugata,
  amrita, dákiní, samádhi, dharmata, mandala, stúpa. Nenahrazuj je českými opisy.
- Používej zavedenou českou buddhistickou terminologii: útočiště, zásluhy, věnování,
  bytosti, říše, zatemnění, soucit, Tři klenoty.
- Rubriky (instrukce) piš v rozkazovacím způsobu **2. osoby množného čísla**:
  připravte, vizualizujte, recitujte, proneste. (Vzory: recitujte 14×, vizualizujte
  9×, singulár 0×.)
- Vlastní jména v české transkripci: Džigme Lingpa, Rangdžung Dordže, Orgjen Tobgjal
  Rinpočhe, Longčhen Ňingtik, Mipham Rinpočhe, Šákja Šrí, Guru Rinpočhe, Padmasambhava.
- Konzistence: jeden tibetský termín = jedno české ustálené řešení v celém textu.
- Výstup: očíslované segmenty přesně podle source.md, pouze čeština, jeden překlad na
  segment.

### Česká formulace (nejčastější zdroj vad; čti pozorně)

- **Neopakuj totéž slovo ve dvou sousedních řádcích**, ani když ho opakuje tibetština
  — sáhni po synonymu nebo řádek přeformuluj. Vzory synonyma mají: esence / podstata,
  klam (12×) / zmatení (9×) / iluze (20×). Zákaz neplatí na refrén, kde je opakování
  zjevný záměr. Špatně: „Esencí prázdné vědomí… / v tobě, esenci všech útočišť…";
  „…bloudí v klamu / kéž se jejich klam rozplyne".
- **Materiál se vyjadřuje předložkou, ne přídavným jménem**: „miska z lebky", „damaru
  z lebek", „mála z lebečních kostí" — nikdy „lebeční miska", „lebeční damaru".
  Přívlastek přidávej jen tam, kde ho tibetština nese (ཐོད = lebka); jinde stačí holý
  termín, jak to dělají vzory: kapála (27×), damaru (12×).
- **Nevymýšlej slova.** „Překážeč" ani „od bezpočátku" nejsou česky. Když si u slova
  nejsi jistý, že existuje, tak neexistuje — opiš to: „tvůrce překážek", „od času bez
  počátku". Totéž platí pro kalky z angličtiny.
- **Termín, který neznáš, ověř ve vzorových překladech, ne odhadem:**

  ```
  grep -ho -i '[^.]*<hledaný výraz>[^.]*' /Users/prokop/texts/reference/mined/*.txt | head
  ```

  Nula výskytů u nově vymyšleného českého termínu je varovný signál, ne povolení.
  Vzorové brožury jsou autorita; když se rozcházejí s tvou intuicí, platí vzory.
- **Anglická transkripce vlastního jména do češtiny nepatří — a ověřuje se počtem.**
  „Dudjom" je anglický zápis; vzory mají **Düdžom 75×** proti Dudjom 1×. Stejně
  „Džigdräl" 15× proti „Džigdral" 1×. Obojí prošlo celým prvním během cyklu Pudri
  Rekpung nepovšimnuto, protože jméno vypadá jako zavedené. Každé vlastní jméno
  protáhni greppem vzorů, i když si jsi jistý; anglické formy (Dudjom, Tsogyal,
  Thinley) se vlévají z bibliografií. Výjimka: bibliografická citace v kolofonu
  zůstává v původním anglickém tvaru verbatim.
- **Přečti si řádek nahlas.** Text se recituje; co se nedá vyslovit jedním dechem
  nebo o co zakopne jazyk, přeformuluj.
- **Verš nezačíná shlukem funkčních slov.** „se s prudkou touhou… klaním", „se ze
  srdce raduji" — reflexivní „se" patří za první silné slovo: „s prudkou touhou a
  vírou se neustále klaním", „ze srdce se raduji". Ve vzorech takový začátek verše
  není a při recitaci o něj jazyk zakopne. (Nejčastější vada korektury: 3 řádky
  v jednom textu.)
- **Rozkazovací způsob, který se čte jako minulý čas, nahraď.** „vyšli sílu soucitu"
  (vyslat) splyne při čtení nahlas s „vyšli" (vyjít) — piš „projev sílu soucitu".
  Hlídej homografy u imperativů obecně.
- **Číslo mluvčího drž podle tibetštiny, ne podle angličtiny.** `bdag` je „já" a
  `bdag la` „mně"; anglické překlady to rutinně mění na „we/us" („grant us the four
  empowerments"), a draft to pak přebere. V Deští požehnání se takhle posunuly čtyři
  segmenty (97, 101, 103, 119) v textu, kde je mluvčí jinak celý singulární. Stejná
  past u čísla podstatných jmen: `lus` = tělo, ne „svá těla".
- **Kde angličtina přeskládala dvojverší, ověř řádkovou korespondenci explicitně.**
  Nejde jen o pořadí celých řádků: anglický překlad často přetahuje na druhý řádek
  koncové slovo prvního (`gdung shugs kyis`, `sgo gsum gyi`) nebo prohodí oslovení
  s rozkazem. Draft to převezme a `compare` ani `check` na to nemají páku — v Deští
  požehnání to byla nejcennější kategorie recenze (7 findingů: 21/22, 52/53, 73/74,
  128/129). Recenzentovi to řekni v promptu jako samostatný úkol.
- **`choť` je femininum**: genitiv singuláru „choti", ne „chotě" (to je mužský tvar);
  instrumentál „s chotí". Vyskytuje se v každém textu s `yab yum`.
- **Slova z počítačové a lékařské češtiny nepatří do praxového textu.**
  „Vygenerování božstva" (vzory: „vytváření", „fáze rozvoje"), „pěti degeneracemi"
  (0 dokladů; česky „pěti úpadky"). Zní odborně, a proto projdou — grep je odhalí.
- **Titul, který se sází dvakrát, kontroluj dvakrát.** Obálka jde z `front.txt`, ale
  segment 1 se sází z draftu; v Deští požehnání zůstalo v druhém výskytu nečeské
  „Padou padající požehnání", zatímco obálka byla v pořádku.
- **Jeden tibetský termín drž v celém textu stejně a variantu rozhodni počtem
  ve vzorech, ne řádek po řádku.** V jednom textu se stejné `klong` přeložilo jako
  prostor i „prostornost" (0× ve vzorech), `kun 'dus` jako ztělesnění i sjednocení
  i vtělení (0×), `grub` jako realizace i uskutečnění — vždy vyhrává doložená
  varianta. Než dopíšeš draft, projdi si vlastní termíny greppem výše.

### Terminologie — jediný zdroj je `glossary.tsv`

Termíny do SKILL.md nepatří: závazný seznam generuje `lotsawa.py glossary --prompt`
a jde v promptu každému překladateli. Dřív tu stály dvě sekce s termy; obě zamrzly na
hodnotách, které glosář už opravil (Ješe Cchogjal, Velkolepý, přiblížení), a rozeslaly
je překladatelům. Proto jsou pravidla, ne seznamy:

- **Jeden glosář pro všechny texty.** Složka cyklu je dávka práce, ne rozsah
  terminologie — per-cycle glosář nikdy nevzniká. Linie u termu je provenience,
  platnost je globální.
- **Autorita jsou vzorové brožury** v `reference/mined/`, a doklad se měří
  **tib-anchored** (`pdfmine.py arbitrate`), ne greppem češtiny: „velkolepý" je
  v referenci 5×, ale u `dpal chen` sedí 10 z 11 bloků na „velký slavný" — ta slova
  tam překládají jiné termy. Grep je indicie, arbitráž rozhoduje.
- `fixed` vyžaduje počet výskytů v `note`. Bez dokladu na žádné straně vyhrává
  **tibetská fonetická transkripce**; sanskrt jen tam, kde ho vzory samy používají
  (Vadžrakumára, Vadžradhara, Jamarádža, Padmasambhava).
- Nový nebo změněný term piš do `glossary.tsv` s počtem v `note`, ne sem a ne jen do
  `notes.md`. `notes.md` drží rozhodnutí o segmentu, glosář drží termín.
- Fonetika není terminologie — pravidla drží [phonetics.md](phonetics.md), měřená na
  vzorech. Starší pravidla skillu („húng ve verši / hung v mantře", `phe`, „koncové -l
  nepřehlasuje") jsou tam **vyvrácena měřením**; `lotsawa.py check` hlásí drift termů
  proti glosáři, takže tenhle rozpor už neprojde tiše.

## Těžba referenčních PDF (hotové vlastní překlady jako autorita)

Hotové interlineární překlady v PDF (tibetština / fonetika / čeština) jsou lepší zdroj
pravdy než odvozená pravidla. Těží je `scripts/pdfmine.py` (potřebuje `pdftotext`
z poppleru; predikáty přebírá z `lotsawa.py`, nic neduplikuje):

```
python3 <skill>/scripts/pdfmine.py triage  reference/            # lze těžit? gate
python3 <skill>/scripts/pdfmine.py extract reference/ -o reference/mined/
python3 <skill>/scripts/pdfmine.py lexicon reference/mined/      # slabika → přepis + konflikty
python3 <skill>/scripts/pdfmine.py bank    reference/mined/      # trojice pro build --reuse-bank
python3 <skill>/scripts/pdfmine.py arbitrate reference/mined/ --glossary <skill>/glossary.tsv
python3 <skill>/scripts/pdfmine.py style   reference/mined/      # expanze vs. náš korpus
```

- **`triage` je gate**: verdikt `text` (Unicode tibetština → plná těžba), `legacy`
  (starý font, tibetština se vytáhne jako latinková hatmatilka → nahlásit, netěžit)
  nebo `scan` (obrysy/sken → čti stránky přímo Readem; tesseract není a tibetské OCR
  je nespolehlivé).
- **Struktura se poznává podle pozice v bloku, ne podle stylu řádku** — fonetika
  v PDF bývá VERZÁLKAMI, takže stylové detektory z `lotsawa.py` na ni nefungují.
- **Zarovnání pro lexikon jen při shodě počtů** (tibetské slabiky vs. fonetické
  tokeny); nezarovnatelný řádek se zahodí, nehádá se.
- **Každý vytěžený řádek nese provenienci** (soubor + strana), jinak nelze rozhodnout
  pozdější spor.
- **Konflikt s `phonetics.md` řeší uživatel, ne skript.** Referenční PDF mohou používat
  jiný systém (transliterace verzálkami: THUG, TSHOG, TRÜL) než pravidla skillu
  (výslovnostní minusky: thuk, cchok, thrul). To je rozhodnutí o konvenci, ne chyba —
  `lexicon` rozdíly jen vypíše.
- **Nové vzorové brožury** patří do `reference/`; pak `pdfmine.py extract` + `lexicon`
  + `bank`. Po každém přetěžení se přepočítá opora glosáře (grep ze Step 3) — termín,
  který nově získal doklady, může povýšit z `prov` na `fixed`, a naopak `fixed` bez
  opory je podezřelý. Víc vzorů je vždy lepší, ale mezera v překladu bývá spíš v tom,
  že se korpusu nikdo nezeptal, než v tom, že by odpověď neznal.

## Cyklový režim (celá složka, desítky textů)

Když uživatel zadá celou složku cyklu (např. „spusť lotsawa na Pudri Rekpung"). Cyklus
je **dávka práce, ne terminologický rozsah** — terminologie zůstává globální:

1. **Pořadí: nejkratší texty první, největší nakonec.** Konvence a fonetické
   kalibrace ustanovené na krátké modlitbě k linii a denní praxi pak platí pro
   569segmentovou sádhanu; obráceně by se velký text překládal naslepo a musel se
   revidovat. Banka tripletů zároveň s každým hotovým textem roste, takže největší
   texty jsou nejlevnější, právě když se k nim dojde.
2. Texty, které se odvolávají na jiné (notace `rol tshig` cituje incipity hlavní
   sádhany; popisky torem používají její terminologii), odlož **za** text, na který
   odkazují.
3. **Sériová je montáž, ne delegace.** Jeden text = jeden úplný běh dle Steps 1–5
   včetně `check`, a porovnání i montáž dělej po jednom — tam se rozhoduje a dvě
   rozdělaná porovnání se pletou. Delegace ale pipelinuj: překladatel a fonetika pro
   text N+1 mohou běžet, když recenzuješ text N. Původní pravidlo zakazovalo
   paralelní překladatele s odůvodněním, že nedokončené texty blokují banku tripletů —
   naměřeno na cyklu Pudri Rekpung to odůvodnění neplatí: `consist` našel mezi čtyřmi
   hotovými texty **jediný** společný tibetský řádek a `build` hlásil `bank 1`.
   Sdílené řádky se soustředí v hlavní sádhaně a textech, které ji citují; tam pořadí
   drž, jinak je čekání zbytečné. Nikdy ale nepouštěj překladatele na pět textů
   zároveň — montáž se stane frontou a přehled se ztratí.
4. Nový nebo změněný term piš průběžně do `glossary.tsv` (s počtem výskytů v `note`)
   a rozhodnutí o segmentu do `drafts/notes.md` textu, kde vzniklo — ne až na konci
   a nikdy do SKILL.md.
5. Realistický odhad: 13 textů (1,5–91 kB) ≈ celý den práce s dávkovými delegacemi;
   100+ textů plánuj po dávkách napříč dny. Cena jednoho Codex draftu byla 50–167 k
   tokenů podle délky textu.
