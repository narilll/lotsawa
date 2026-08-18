# Česká fonetická transkripce tibetštiny

Pravidla pro fonetický řádek pod tibetským veršem a mantrou. Cíl: recitující čte
nahlas bez znalosti tibetštiny i anglických transkripčních konvencí.

**Autorita jsou vzorové texty v `reference/`** (25 brožur, 379 stran). Celý systém
níže je z nich odvozen měřením, ne stanoven odhadem: 1219 slabik lexikonu ze 1263
zarovnaných řádků. Kde se vzory rozcházejí s intuicí, platí vzory.

## Primární postup: lexikon, ne pravidla

```
python3 <skill>/scripts/lotsawa.py pho --source drafts/source.md -o drafts/pho_done.txt
```

Fonetika se **skládá z lexikonu** `reference/mined/pho_lexikon.tsv` (slabika →
přepis). Pokrytí: 89 % slabik našich veršů, 60 % veršů úplně. Verš s neznámou
slabikou jde do `pho_todo.txt` s vyznačeným `???` a řeší se podle pravidel níže —
ostatní se generují mechanicky, takže konvence nemůže kolísat.

Zpětný test generátoru proti vzorům: 62 % znak za znakem, **81 % v rámci jedné
slabiky**. Zbytek jsou rozdíly ve vzorech samotných (táž slabika jednou `GI`, jinde
`GJI`) — generátor drží dominantní tvar, tedy konzistenci, kterou zdroj sám nemá.

## Lexikon není důvěryhodný sám o sobě

**444 z 1254 záznamů stojí na jediném zarovnání** a `load_lexicon` jim dává
spolehlivost 1,0, protože nemají alternativu. `pho` proto u každého běhu vypíše, které
slabiky na takovém záznamu stojí — ten seznam je nutné projít, ne přeskočit.

V cyklu Pudri Rekpung se takhle našlo **hnízdo sedmi vadných záznamů z jedné stránky
jednoho PDF**: ta stránka nese IAST poznámkový blok a zarovnávač ho pobral jako
fonetický řádek. Výsledek: `སརྦ→TRI`, `བིགྷྣཱན→VIGHNĀN`, `བཾ→BAṂ`, `ཛཿ→JAḤ`, `ཏྲི→NṚ`,
`ནྲྀ→E`, `ཏྱཾ→ŚATRŪN`. Tři z nich v jedné mantře vyrobily „TRI VIGHNĀN BAM" místo
„SARVA BIGHNAN BAM". U `ཛཿ` měl lexikon správné `DZA` dokonce jako alternativu se
shodným počtem — **remízu 1:1 vyřešil ve prospěch poznámky pod čarou**.

Dvě poznávací znamení kontaminace:

1. **IAST diakritika** (`Ṛ Ṣ Ṇ Ṭ Ḍ Ḥ Ṃ Ā Ī Ū Ś`) ve zvolené hodnotě. Konvence ji
   zakazuje, takže její přítomnost znamená, že hodnota nepřišla z fonetického řádku.
   Po opravě 2026-07-29 je v lexikonu **nula** takových hodnot — když se nějaká
   objeví, je to nové kontaminované těžení.
2. **Shodná provenience u víc podezřelých záznamů.** Když dvě vadné slabiky odkazují
   na tutéž stránku, prověř všechny záznamy z té stránky, ne jen ty dvě.

Po každém `pdfmine.py lexicon` proto: `awk -F'\t' '$2 ~ /[ṚṢṆṬḌḤṂĀĪŪŚ]/' pho_lexicon.tsv`
musí být prázdné, a záznamy s počtem 1 sdílející jednu stránku projdi hromadně.

## Systém

| Vlastnost | Pravidlo | Doklad ve vzorech |
|---|---|---|
| Písmo | **VERZÁLKY** | 7719 vs. 3 výskyty |
| Dělení | **jedna tibetská slabika = jeden token**, kromě slitých složenin níže | délka tokenu 2–4 znaky |
| Délky | **žádné** — jen `Ä Ö Ü` | `É Í Ú Ó` se nevyskytují |
| Apostrof | zachovává se (`BU’I`, `WO’I`) | 339× |

### Souhlásky

| tibetsky | přepis | příklad |
|---|---|---|
| ཅ / ཆ | Č / **ČH** | ČE, ČHOG |
| ཙ / ཚ | TS / **TSH** | TSÄL, TSHOG |
| ཇ, འཇ, བྱ | **DŽ** | DŽE, DŽIN |
| ཞ, གཞ, བཞ | **Ž** | ŽING |
| ཤ, གཤ | **Š** | ŠE |
| ཉ, སྙ, མྱ | **Ň** | ŇI, ŇING |
| ཀྱ / ཁྱ / གྱ | KJ / KHJ / **GJ** | KJE, GJÄL |
| ཁྲ, འཁྲ, ཕྲ, འཕྲ | **THR** nebo TR (viz níže) | THRIN LE |
| ཐ, མཐ / ཕ, འཕ / ཁ, མཁ | TH / PH / KH | THUG, PHET, KHA |
| ཡ | **J** | JE, JING |
| ཝ, བ (v pozici) | W / B | WANG, WA |

`CCH` neexistuje — sykavka je vždy `TSH`.

### Koncovky (nejdůležitější rozdíl proti intuici)

| tibetská koncovka | co se stane | příklad |
|---|---|---|
| ག, བ, ལ, མ, ན, ར | **píše se** | THU**G**, DRU**B**, SÖ**L**, DA**M**, KÜ**N**, NO**R** |
| ས | **mizí**, přehlasuje samohlásku | ཐུགས → THUG, ཤེས → ŠE, རུས → RÜ |
| ད | **mizí**, přehlasuje samohlásku | ཐོད → THÖ, ཉིད → ŇI, མེད → ME |

Přehláska: `o → Ö`, `u → Ü`, `e → E`, `i → I`. Doklady: ག→G 489×, ལ→L 437×,
ད→Ö 247×/E 224×, ས→G 513×/E 398×.

**Pozor**: koncové `-l` přehlasuje a zůstává (གསོལ → **SÖL**, 24×). Starší pravidlo
skillu („koncové -l nepřehlasuje, gsol → sol") bylo měřením vyvráceno.

### Nejednoznačné slabiky — jeden globální tvar

Vzory samy kolísají; skill drží první variantu (dominantní ve vzorech):

| tibetsky | zvoleno | varianta ve vzorech |
|---|---|---|
| གི, གིས | **GJI** | GI (28× vs. 27× — téměř nerozhodně) |
| བར | **BAR** | WAR (18× vs. 16×) |
| དཔལ | **PÄL** | PAL (15× vs. 9×) |
| ཁྲག | **TRAG** | THRAG (19× vs. 6×) |
| འཕྲུལ, འཁྲུལ | **TRÜL** | THRÜL (15× vs. 6×, 10× vs. 7×) |
| ཨ | **AH** | A (13× vs. 5×) |
| བྱིན | **DŽIN** | ČHIN (14× vs. 3×) |

### Slité složeniny — výjimka z pravidla „slabika = token"

Lexikon je slabikový, takže slité tokeny **vyrobit nedokáže** a `pho` je vždy rozdělí.
Vzory je přitom slévají zcela jednoznačně, u vlastních jmen i ustálených složenin:

| tibetsky | vzory slitě | vzory rozděleně |
|---|---|---|
| མཁའ་འགྲོ | **KHANDRO** 465× | KHA DRO 0× |
| ཡེ་ཤེས | **JEŠE** 97× | JE ŠE 6× |
| གུ་རུ | **GURU** 34× | GU RU 1× |
| བླ་མ | **LAMA** 24× | LA MA 7× |
| གསོལ་བ | **SÖLWA** 24× | SÖL WA 1× |
| ཨོ་རྒྱན | **ORGJEN** 25× | O GJEN 0× |
| འོད་ཟེར | **ÖZER** 9× | Ö ZER 3× |
| མཚོ་རྒྱལ | **TSHOGJÄL** 2× | TSHO GJÄL 1× |

Oba testy proti korpusu (oba odhalily reálné vady) dělá `pho` sám nebo je jeden
příkaz — **neskládej si grepy ručně**:

1. **bigramy — automaticky.** `pho` pro každou sousední dvojici tokenů srovná počet
   `A B` a `AB` na fonetických řádcích vzorů a kde slitý tvar vyhrává, slije ho;
   provedená slití vypíše (`sloučeno dle vzorů: N×`). Vypnout jde `--no-merge`.
   Test na pouhé slepení nechytá vsunuté `n` (KHA + DRO → KHA**N**DRO) ani
   trojslabičné složeniny — takové případy hledej podle tibetské složeniny, ne podle
   latinky. Pozor i na opačný případ: **specifická složenina bije obecný počet.**
   U `ཡེ་ཤེས་སེམས་དཔའ་` (džňánasattva) mají vzory `JE ŠE SEM PA` 1× a `JEŠE SEM` 0×,
   takže se tam neslévá, i když obecné `JEŠE` vyhrává 145:8.
2. **neznámé tokeny** — `lotsawa.py cz '<TOKEN>' --pho`. Token, který se ve vzorech
   nevyskytuje ani jednou, je podezřelý. Příkaz zároveň hlásí, když jsou doklady jen
   uvnitř jiných slov, což je u fonetiky snadná past: `THRI` má jako podřetězec 40
   výskytů, ale všechny uvnitř `THRIN` (phrin las) — jako samostatný token **0×**.
   Legitimní výjimky: sanskrt v mantrách (AWAŠAJA) a doložené vzorce koncovek
   (`TSE’I` podle `DŽE’I` 36×). Aspirace může držet rozlišení mezi slovy, i když je
   tvar nedoložený: `ཐེར` → `THER` (0×), protože `TER` (21×) je གཏེར, terma.

`THÖ THRENG TSÄL` naopak zůstává **rozdělené ve verši** (7×) a slité
**v mantře** (THÖTHRENGTSÄL) — vzory to takto rozlišují.

## Mantry

- **Dva řádky: tibetština + fonetika. Žádný řádek IAST** — vzory jej neobsahují.
- Týž systém jako u veršů: verzálky, bez délek.
- `ཧཱུྃ` → **HUNG** vždy (41×; rozdíl „húng ve verši / hung v mantře" ve vzorech
  neexistuje). `ཕཊ` → **PHET** (43×). `བཛྲ` → **BENDZA**. `པདྨ` → **PEMA**.
- Příklad: `ༀ་བཛྲ་ཀཱི་ལི་ཀཱི་ལ་ཡ་ཧཱུྃ་ཕཊ༔` → `OM BENDZA KILI KILAJA HUNG PHET`

## Vlastní jména v českém překladu

Překlad a kolofon používají tentýž systém, ale s velkým počátečním písmenem jako
vlastní jména: Padmasambhava, Ješe Tsogjäl, Džigme Phüntsok, Dordže Drolö.
Sanskrtská jména božstev zůstávají v sanskrtu s českým pravopisem (Vadžrakumára,
Amitábha, Jamarádža).

## Co se změnilo proti dřívější konvenci skillu (2026-07)

Skill dřív používal výslovnostní minusky s délkami (`thuk`, `čhok`, `cchok`, `húng`,
`phe`, `sol`) a mantry o třech řádcích s IAST. Vzorové texty používají jiný systém —
transliteraci verzálkami se zachovanými koncovkami. Přechod na vzory znamená, že
dříve vygenerované texty jsou ve staré konvenci; přegenerují se.
