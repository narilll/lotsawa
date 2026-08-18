#!/usr/bin/env python3
"""Mechanické kroky workflow lotsawa: segmentace, porovnání draftů, montáž, lint.

Usage:
  lotsawa.py segment original.md -o drafts/source.md [--delim auto|terma|shad]
  lotsawa.py compare --source drafts/source.md --draft F=a.md[,b.md] --draft C=c.md
                     [-o drafts/review.md] [--ratio 0.4]
  lotsawa.py build --source drafts/source.md --base drafts/fable-tib.md [--base ...]
                   [--reuse ../] [--pho drafts/pho_done.txt] [--mantra drafts/mantra_done.txt]
                   [--overrides drafts/overrides.json] [--front f.txt] [--back b.txt]
                   -o text.md [--dry-run] [--allow-gaps]
  lotsawa.py check text.md [--source drafts/source.md] [--original original.md]
  lotsawa.py concord <tibetský termín> [--root ...] [--translated-only|--originals-only]
  lotsawa.py glossary --corpus "<dir s texty>" [--prompt | --check]
  lotsawa.py pho --source drafts/source.md -o drafts/pho_done.txt
  lotsawa.py meter text.md [--max-ratio 4.56]
  lotsawa.py czech text.md > drafts/czech.txt
  lotsawa.py selftest

Ztráta nebo poškození dat je fatální (exit 1); redakční soud je varování (exit 0).
Chybějící fonetika je stav, ne chyba: build zapíše *_todo.txt a skončí s exit 2.
Stdlib only.
"""
import argparse
import difflib
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

TIB = 'ༀ-࿿'
TIB_RE = re.compile(f'[{TIB}]')
PUNCT_ONLY_RE = re.compile(f'^[་།༎༈༔༄༅༃\\s]+$')
SANSKRIT_MARKS = 'ཾཿཱྃྂ'          # ཾ ཿ ྃ ྂ ཱ
SANSKRIT_SUBJOINED = 'ྵྡྞྚྷ'      # ྵ ྜ ྞ ྚ ྷ
PROSE_MARKERS = ('ཞེས', 'ཅེས', 'སོགས',
                 'བྱའོ')               # ཞེས ཅེས སོགས བྱའོ
SHAD, NYIS_SHAD, SBRUL_SHAD, TERMA_SHAD, TSHEG = '།', '༎', '༈', '༔', '་'

_warn = 0
_err = 0


def warn(sub, msg):
    global _warn
    _warn += 1
    print(f'WARN {sub}: {msg}', file=sys.stderr)


def err(sub, msg):
    global _err
    _err += 1
    print(f'ERROR {sub}: {msg}', file=sys.stderr)


def finish(sub, exit_on_error=True):
    print(f'{_warn} warnings, {_err} errors', file=sys.stderr)
    if _err and exit_on_error:
        sys.exit(1)
    return _err


# ---------------------------------------------------------------- shared core

def norm_tib(s):
    """Pro rekonstrukční srovnání: zahazuje jen whitespace, nic jiného."""
    return re.sub(r'\s+', '', s)


# Ortografické varianty téhož slova napříč zdroji. Doloženo na Sedmiřádkové
# modlitbě: vzorové brožury píší ཡུལ་གི a ཞེས་སུ་གགས, náš zdroj ཡུལ་གྱི a ཞེས་སུ་གྲགས,
# a slabika HUNG nese ྂ / ྃ / ཾ podle sazby. Folduje se JEN klíč banky — překlad,
# fonetika ani rekonstrukční kontrola (norm_tib) se nemění.
KEY_EQUIV = [('གྱི', 'གི'), ('གྲགས', 'གགས'), ('ྂ', 'ྃ'), ('ཾ', 'ྃ'), ('ཿ', '')]


def key_tib(s):
    """Klíč banky tripletů: bez interpunkce a tsheg, aby སྟེང་༔ == སྟེང༔.

    Navíc srovnává ortografické varianty z KEY_EQUIV, jinak se týž verš ze dvou
    brožur nepotká.
    """
    s = re.sub(f'[\\s{TSHEG}{SHAD}{NYIS_SHAD}{SBRUL_SHAD}{TERMA_SHAD}༄༅༃]', '', s)
    for a, b in KEY_EQUIV:
        s = s.replace(a, b)
    return s


VISARGA = 'ཿ'          # rnam bcad — ukončuje slabiku i bez tsheg (ཨཱཿཧཱུྃ = 2 slabiky)


def syl(s):
    """Počet slabik: tsheg + 1 po odstranění interpunkce (0 pro netibetský text).

    `ཿ` se počítá jako dělítko: bez toho je ཨཱཿཧཱུྃ jedna slabika, počty vyjdou
    o jednu nižší a zarovnání fonetiky se tiše posune (v mantře Vadžraguru
    ཨོཾ་ཨཱཿཧཱུྃ་བཛྲ… to posunulo celý zbytek řádku).
    """
    core = re.sub(f'[^{TIB}]', '', s)
    core = re.sub(f'[{SHAD}{NYIS_SHAD}{SBRUL_SHAD}{TERMA_SHAD}༄༅༃]', '', core)
    core = re.sub(f'{VISARGA}(?=[^{TSHEG}])', VISARGA + TSHEG, core)
    core = core.strip(TSHEG)
    if not core:
        return 0
    return core.count(TSHEG) + 1


def has_tib(s):
    return bool(TIB_RE.search(s))


def is_punct_only(s):
    return bool(s.strip()) and bool(PUNCT_ONLY_RE.match(s)) and not re.search(f'[{TIB}]', re.sub(
        f'[{TSHEG}{SHAD}{NYIS_SHAD}{SBRUL_SHAD}{TERMA_SHAD}༄༅༃]', '', s))


def pho_tokens(line):
    return [t for t in re.split(r'[^\wáéíóúýčďě'
                               r'ňřšťůžüö]+', line.lower()) if t]


def looks_like_pho(line):
    """Fonetický řádek: jednotné psaní (VERZÁLKY dle vzorů, nebo minusky u starých
    textů) a bez věcné interpunkce.

    Vzorové texty píšou fonetiku verzálkami, starší výstupy skillu minuskami — obojí
    musí projít, jinak přestane fungovat vše, co na tomhle predikátu stojí
    (czech_lines, verse_triplets, banka, meter, check). Odmítá se jen věta, tj. řádek
    s malými i velkými písmeny zároveň, jak ho píše česká próza.
    """
    s = line.strip()
    if not s:
        return False
    if re.search(r'[,!?;:]', s):
        return False
    letters = [ch for ch in s if ch.isalpha()]
    if not letters:
        return False
    upper = sum(1 for ch in letters if ch.isupper())
    return upper == len(letters) or upper == 0


def fold(s):
    """Bez diakritiky a malými písmeny — pro srovnávání českých kořenů.

    Čeština palatalizuje (pohřebiště → pohřebišť), takže kořen „pohřebišt" by
    inflektovaný tvar nenašel; po fold() se oba shodnou na „pohrebist".
    """
    nfd = unicodedata.normalize('NFD', s.lower())
    return ''.join(ch for ch in nfd if not unicodedata.combining(ch))


IAST_CHARS = 'ṃḥāīūṣṭḍñṛśḷṇ'


def looks_like_iast(line):
    return any(ch in IAST_CHARS for ch in line) or ' | ' in line


def czech_lines(lines, i):
    """Všechny české řádky jednotky, která začíná tibetským řádkem na indexu i.

    Vrací [] pro mantru (druhý řádek je fonetika, ne čeština). Vrací víc řádků
    u titulních bloků (titul + autor) a u rubrik s víceřádkovým překladem — hledat
    termín se musí ve všech, jinak vznikají falešné nálezy.

    Fonetika se pozná **pozicí v bloku, ne stylem řádku**: stojí hned za tibetštinou.
    Stylový test na ni nestačí — `looks_like_pho` bere za fonetiku i český verš bez
    interpunkce psaný malými písmeny („kéž se jejich klam rozplyne"), takže filtr přes
    celý blok takové verše tiše zahazoval a kontrola glosáře je nikdy neviděla.
    """
    unit = []
    for l in lines[i + 1:i + 5]:
        if not l.strip() or has_tib(l):
            break
        unit.append(l)
    if unit and looks_like_iast(unit[-1]):
        return []
    if unit and looks_like_pho(unit[0]):
        if len(unit) > 1:
            unit = unit[1:]                # verš/titul: fonetika (nebo titul) je první
        elif unit[0].strip() == unit[0].strip().upper():
            return []                      # mantra: tibetština + fonetika VERZÁLKAMI
    return unit


# ------------------------------------------------------------ source.md model

class Seg:
    __slots__ = ('num', 'type', 'tib', 'uncertain')

    def __init__(self, num, type_, tib, uncertain=False):
        self.num, self.type, self.tib, self.uncertain = num, type_, tib, uncertain


SEG_RE = re.compile(r'^## (\d+(?:\.\d+)?) \[(\w+)(\?)?\]\s*$')


def parse_source(path):
    segs = {}
    cur = None
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        m = SEG_RE.match(line)
        if m:
            cur = Seg(m.group(1), m.group(2), '', bool(m.group(3)))
            segs[cur.num] = cur
        elif cur is not None and line.startswith('tib:'):
            cur.tib = line[4:].strip()
    return segs


def parse_draft(path):
    """Tolerantní parser: hlavička, pak všechny neprázdné řádky slité mezerou."""
    out = {}
    cur, buf = None, []
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        m = SEG_RE.match(line)
        if m:
            if cur is not None:
                out[cur] = ' '.join(buf).strip()
            cur, buf = m.group(1), []
        elif cur is not None and line.strip() and not line.startswith(('tib:', '#')):
            buf.append(line.strip())
    if cur is not None:
        out[cur] = ' '.join(buf).strip()
    return out


def merge_drafts(paths):
    merged, origin = {}, {}
    for p in paths:
        for num, txt in parse_draft(p).items():
            if num in merged:
                err('compare', f'segment {num} je ve dvou dílech ({origin[num]}, {p})')
            merged[num] = txt
            origin[num] = p
    return merged


# --------------------------------------------------------------- 1. segment

def split_units(text, mode):
    """Rozdělí na jednotky. Interpunkce patří k předchozí jednotce, ༈ k následující."""
    if mode == 'terma':
        pat = f'(?<=[{TERMA_SHAD}])'
    else:
        # hranice je za celým během shadů (`། །`, `།།`, `༎`) včetně mezer v něm
        pat = f'(?<=[{SHAD}{NYIS_SHAD}])(?![\\s]*[{SHAD}{NYIS_SHAD}])'
    parts = [p for p in re.split(pat, text) if p.strip()]
    # ༈ a ༄ zahajují novou jednotku
    out = []
    for p in parts:
        pieces = re.split(f'(?=[{SBRUL_SHAD}༄])', p)
        out.extend(x for x in pieces if x.strip())
    return merge_bare(out)


def merge_bare(units):
    """Jednotka bez tibetské litery se slévá do předchozí; úvodní ༄༅། ། do následující."""
    merged, pending = [], ''
    for u in units:
        bare = re.sub(f'[{SHAD}{NYIS_SHAD}{SBRUL_SHAD}{TERMA_SHAD}༄༅༃{TSHEG}\\s]', '', u)
        if not has_tib(bare):
            if merged:
                merged[-1] += u
            else:
                pending += u
        else:
            merged.append(pending + u)
            pending = ''
    if pending:                      # celý text bez jediné tibetské litery
        merged.append(pending)
    return [u.strip() for u in merged if u.strip()]


def split_intro(unit):
    """Druhý průchod na dlouhý blok bez ༔: verše po shadech, próza slitá."""
    pieces = [p for p in re.split(f'(?<=[{SHAD}{NYIS_SHAD}])(?![{SHAD}{NYIS_SHAD}\\s])', unit)
              if p.strip()]
    typed = []
    for p in pieces:
        s = p.strip()
        n = syl(s)
        inner = re.sub(f'[{SHAD}{NYIS_SHAD}\\s]+$', '', s)
        is_verse = (5 <= n <= 11
                    and re.search(f'[{SHAD}{NYIS_SHAD}]\\s*$', s)
                    and SHAD not in inner
                    and not any(mk in s for mk in PROSE_MARKERS))
        typed.append(('verse' if is_verse else 'prose', s))
    # slij sousedící prózu; verše nikdy
    out = []
    for kind, s in typed:
        if kind == 'prose' and out and out[-1][0] == 'prose':
            out[-1] = ('prose', out[-1][1] + ' ' + s)
        else:
            out.append((kind, s))
    return out


def classify(unit, first, last):
    n = syl(unit)
    core = re.sub(f'[^{TIB}]', '', unit)
    if first and '༄' in unit:
        return 'heading', False
    marked = sum(1 for ch in core if ch in SANSKRIT_MARKS or ch in SANSKRIT_SUBJOINED)
    if n and marked / max(n, 1) >= 0.5:
        return 'mantra', False
    if last:
        if unit.lstrip().startswith(('ཅེས', 'ཞེས')):  # ཅེས ཞེས
            return 'colophon', False
        warn('segment', f'poslední jednotka nezačíná ཅེས/ཞེས — typuji jako rubric, ne colophon')
    inner = re.sub(f'[{SHAD}{NYIS_SHAD}\\s]+$', '', unit)
    if SHAD in inner:
        return 'rubric', False
    if n <= 9:
        return 'verse', False
    if n <= 14:
        return 'verse', True          # šedá zóna
    return 'rubric', False


def cmd_segment(args):
    original = Path(args.original).read_text(encoding='utf-8').strip()
    mode = args.delim
    if mode == 'auto':
        mode = 'terma' if original.count(TERMA_SHAD) >= 2 else 'shad'
    units = split_units(original, mode)

    expanded = []
    for i, u in enumerate(units):
        needs_split = mode == 'terma' and (TERMA_SHAD not in u or syl(u) > 40)
        if needs_split and syl(u) > 11:
            pieces = split_intro(u)
            # slij interpunkční zbytky (osamocené ༄༅། ། mezi titulem a tělem)
            kinds = {key_tib(p): k for k, p in pieces}
            for piece in merge_bare([p for _, p in pieces]):
                expanded.append((piece, kinds.get(key_tib(piece)) == 'verse'))
        else:
            expanded.append((u, None))

    segs, uncertain = [], []
    for i, (u, forced_verse) in enumerate(expanded):
        # tib: je jednořádkové pole — vnitřní zlomy by se při zápisu ztratily
        u = re.sub(r'\s+', ' ', u).strip()
        first, last = i == 0, i == len(expanded) - 1
        if forced_verse is True:
            t, unc = 'verse', False
        elif forced_verse is False:
            t, unc = ('heading', False) if (first and '༄' in u) else ('rubric', False)
        else:
            t, unc = classify(u, first, last)
        segs.append(Seg(str(len(segs) + 1), t, u, unc))
        if unc:
            uncertain.append(len(segs))

    # --- fatální invarianty
    recon = norm_tib(''.join(s.tib for s in segs))
    if recon != norm_tib(original):
        a, b = norm_tib(original), recon
        off = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
        err('segment', f'rekonstrukce selhala na offsetu {off}\n'
                       f'  originál: …{a[max(0,off-40):off+40]}…\n'
                       f'  segmenty: …{b[max(0,off-40):off+40]}…')
    for s in segs:
        if not s.tib.strip():
            err('segment', f'segment {s.num} je prázdný')
        if is_punct_only(s.tib):
            err('segment', f'segment {s.num} obsahuje jen interpunkci: {s.tib!r}')
    if _err:
        finish('segment')

    if uncertain:
        warn('segment', f'nejistý typ (šedá zóna 10–14 slabik) u segmentů: '
                        f'{", ".join(map(str, uncertain))}')

    note = args.note or f'auto-segmentace ({mode} režim), typy heuristické'
    lines = [f'# source — {note}', f'# {len(segs)} segmentů; sufix ? = nejistý typ', '']
    for s in segs:
        lines.append(f'## {s.num} [{s.type}{"?" if s.uncertain else ""}]')
        lines.append(f'tib: {s.tib}')
        lines.append('')
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text('\n'.join(lines), encoding='utf-8')
    counts = Counter(s.type for s in segs)
    print(f'{args.out}: {len(segs)} segmentů ({mode}) — '
          + ', '.join(f'{k} {v}' for k, v in sorted(counts.items())))
    return finish('segment')


# --------------------------------------------------------------- 2. compare

def cmd_compare(args):
    src = parse_source(args.source)
    # dělené běhy: --draft F=a.md --draft F=b.md (čárka nelze, názvy složek ji obsahují)
    by_label = {}
    for spec in args.draft:
        label, _, path = spec.partition('=')
        by_label.setdefault(label, []).append(path)
    drafts = {label: merge_drafts(paths) for label, paths in by_label.items()}

    out = ['# compare']
    out.append('## pokrytí')
    for label, d in drafts.items():
        missing = sorted(set(src) - set(d), key=lambda x: float(x))
        extra = sorted(set(d) - set(src), key=lambda x: float(x))
        status = 'ok' if not missing and not extra else 'CHYBA'
        out.append(f'{label} {len(d)}/{len(src)} {status}')
        if missing:
            err('compare', f'{label}: chybí segmenty {missing[:20]}')
        if extra:
            err('compare', f'{label}: přebývají segmenty {extra[:20]}')

    out.append('## kontaminace tibetskou interpunkcí v českém řádku')
    contam = {}
    for label, d in drafts.items():
        bad = [n for n, t in d.items() if has_tib(t)]
        contam[label] = len(bad) / max(len(d), 1)
        flag = '  -- NEPOUŽÍVAT JAKO ZÁKLAD' if contam[label] >= 0.10 else ''
        out.append(f'{label} {len(bad)}/{len(d)} segmentů ({contam[label]:.0%}){flag}')
        if bad:
            warn('compare', f'{label}: tibetská interpunkce v {len(bad)} českých řádcích')
    base = min(contam, key=lambda k: contam[k]) if contam else '?'
    out.insert(1, f'base doporučen: {base}')

    labels = list(drafts)
    if len(labels) >= 2:
        a, b = labels[0], labels[1]
        low = []
        for n in sorted(src, key=lambda x: float(x)):
            ta, tb = drafts[a].get(n, ''), drafts[b].get(n, '')
            if ta.strip() == '—' or tb.strip() == '—':
                continue
            norm = lambda s: re.sub(r'\s+', ' ', s.casefold()).strip()
            r = difflib.SequenceMatcher(None, norm(ta), norm(tb)).ratio()
            if r < args.ratio:
                low.append((n, r, ta, tb))
        out.append(f'## k revizi (ratio < {args.ratio:.2f})   {len(low)} segmentů')
        for n, r, ta, tb in low:
            out.append(f'{n}  {r:.2f}  [{src[n].type}] {src[n].tib[:60]}')
            out.append(f'  {a}: {ta[:200]}')
            out.append(f'  {b}: {tb[:200]}')
        disputed = sorted({n for n in src
                           if (drafts[a].get(n, '').strip() == '—')
                           != (drafts[b].get(n, '').strip() == '—')}, key=lambda x: float(x))
        out.append('## sporné mantry (jeden draft dal —, druhý překlad)   '
                   + (' '.join(disputed) if disputed else '(žádné)'))
        if disputed:
            warn('compare', f'sporné mantry: {" ".join(disputed)}')

    text = '\n'.join(out) + '\n'
    if args.out:
        Path(args.out).write_text(text, encoding='utf-8')
        print(f'{args.out}: base={base}, k revizi {len(low) if len(labels)>=2 else 0}')
    else:
        print(text)
    return finish('compare')


# ----------------------------------------------------------------- 3. build

def front_matter_end(lines):
    """Index za titulním blokem: první běh ≥ 5 prázdných řádků + následující titul."""
    blanks = 0
    for i, l in enumerate(lines):
        blanks = blanks + 1 if not l.strip() else 0
        if blanks >= 5:
            return i + 6
    return 0


def load_bank(reuse_dir, exclude_dir=None):
    """key_tib(tib) -> (pho|None, cz) ze všech sourozeneckých text.md (bez titulního bloku).

    `exclude_dir` vynechá jednu složku — typicky tu, do které se právě staví. Bez toho
    čte druhý build vlastní předchozí výstup a banka (která má přednost před --pho
    i --base) tiše zahodí opravu fonetiky nebo základu.
    """
    variants = {}
    excl = Path(exclude_dir).resolve() if exclude_dir else None
    for tm in sorted(Path(reuse_dir).glob('*/text.md')):
        if excl is not None and tm.parent.resolve() == excl:
            continue
        lines = tm.read_text(encoding='utf-8').split('\n')
        i = front_matter_end(lines)
        while i < len(lines) - 1:
            if has_tib(lines[i]) and lines[i + 1].strip() and not has_tib(lines[i + 1]):
                third = lines[i + 2] if i + 2 < len(lines) else ''
                if looks_like_pho(lines[i + 1]) and third.strip() and not has_tib(third):
                    entry = (lines[i + 1], third)
                    i += 3
                else:
                    entry = (None, lines[i + 1])
                    i += 2
                variants.setdefault(key_tib(lines[i - len(entry) - (1 if entry[0] else 0)]
                                            if False else ''), None)
                variants.setdefault(key_tib(lines[i - (3 if entry[0] else 2)]), []).append(entry)
                continue
            i += 1
    bank = {}
    for k, vs in variants.items():
        if not vs:
            continue
        czs = Counter(v[1] for v in vs)
        if len(czs) > 1:
            warn('build', f'banka: různé překlady téhož řádku — {list(czs)[:2]}')
        best_cz = czs.most_common(1)[0][0]
        pho = next((v[0] for v in vs if v[0] and v[1] == best_cz), None)
        bank[k] = (pho, best_cz)
    return bank


def load_tsv(path, cols=1):
    out = {}
    if not path:
        return out
    for raw in Path(path).read_text(encoding='utf-8').splitlines():
        if not raw.strip():
            continue
        parts = raw.rstrip('\n').split('\t')
        if len(parts) < cols + 1:
            err('build', f'{path}: řádek nemá {cols + 1} polí: {raw[:60]!r}')
            continue
        if cols == 1:
            out[parts[0]] = parts[1]
        else:
            out.setdefault(parts[0], {})[parts[1]] = parts[2]
    return out


def lint_pho(num, seg_type, pho):
    """Kontroly podle konvence vzorových textů (viz phonetics.md)."""
    letters = [ch for ch in pho if ch.isalpha()]
    if letters and any(ch.islower() for ch in letters):
        warn('build', f'seg {num}: fonetika se píše VERZÁLKAMI: {pho[:40]}')
    if re.search(r'[áéíóúůý]', pho, re.I):
        warn('build', f'seg {num}: fonetika nenese délky (jen Ä Ö Ü): {pho[:40]}')
    if re.search(r'\bPHE\b', pho, re.I):
        warn('build', f'seg {num}: ཕཊ se přepisuje PHET, ne PHE')
    if re.search(r'\bCCH', pho, re.I):
        warn('build', f'seg {num}: sykavka se píše TSH, ne CCH: {pho[:40]}')


def token_check(new_pho_lines, bank):
    corpus = Counter()
    for pho, _ in bank.values():
        if pho:
            corpus.update(pho_tokens(pho))
    known = list(corpus)
    for num, line in new_pho_lines:
        for tok in pho_tokens(line):
            if tok in corpus:
                continue
            near = [c for c in difflib.get_close_matches(tok, known, n=3, cutoff=0.85)
                    if corpus[c] >= 3]
            if near:
                warn('build', f'seg {num}: „{tok}" (nové) vs '
                              + ', '.join(f'„{c}" ({corpus[c]}×)' for c in near))


def cmd_build(args):
    src = parse_source(args.source)
    base = merge_drafts(args.base)
    own = Path(args.out).resolve().parent if args.out else None
    bank = load_bank(args.reuse, exclude_dir=own) if args.reuse else {}
    if args.reuse_bank:                      # triplety ze vzorových textů
        for line in Path(args.reuse_bank).read_text(encoding='utf-8').splitlines():
            if line.startswith('#') or not line.strip():
                continue
            f = line.split('\t')
            if len(f) >= 3:
                bank.setdefault(f[0], (f[1], f[2]))
    lex = load_lexicon(args.lexicon) if args.lexicon else {}
    pho = load_tsv(args.pho)
    mantra = load_tsv(args.mantra, cols=2)
    overrides = json.loads(Path(args.overrides).read_text(encoding='utf-8')) if args.overrides else {}

    # rozklad segmentů dle overrides na podjednotky
    units = []      # (id, type, tib, cz_or_None)
    for num in sorted(src, key=lambda x: float(x)):
        seg = src[num]
        if num in overrides:
            for j, (t, tib, cz) in enumerate(overrides[num], 1):
                units.append((f'{num}.{j}', t, tib, cz))
            covered = norm_tib(''.join(x[1] for x in overrides[num]))
            if covered != norm_tib(seg.tib):
                err('build', f'override segmentu {num} nepokrývá celý tibetský obsah')
        else:
            units.append((num, seg.type, seg.tib, None))

    missing_pho, missing_mantra, out, prov, new_pho = [], [], [], Counter(), []
    for uid, t, tib, cz_override in units:
        key = key_tib(tib)
        if t == 'mantra':
            # Vzory mají mantru o DVOU řádcích (tibetština + fonetika), bez IAST.
            m = mantra.get(uid)
            pho_m = (m or {}).get('pho')
            if not pho_m and key in bank and bank[key][0]:
                pho_m = bank[key][0]; prov['bank'] += 1
            elif not pho_m and lex:
                cand, unknown = render_pho(tib, lex)
                if not unknown:
                    pho_m = cand; prov['lexikon'] += 1
            elif pho_m:
                prov['mantra_done'] += 1
            if pho_m:
                lint_pho(uid, t, pho_m)
                out.append((tib, None, pho_m))
            else:
                missing_mantra.append((uid, tib))
                out.append((tib, None, 'PHO?')); prov['missing'] += 1
            continue
        cz = cz_override or (bank[key][1] if key in bank else base.get(uid, ''))
        if not cz:
            err('build', f'segment {uid} nemá překlad v žádném draftu')
            cz = 'PHO?'
        cz = re.sub(f'[{TIB}]+', '', cz).strip() if has_tib(cz) else cz
        if t in ('verse',):
            p = (bank[key][0] if key in bank and bank[key][0] else pho.get(uid))
            if not p and lex:
                cand, unknown = render_pho(tib, lex)
                if not unknown:
                    p = cand; prov['lexikon'] += 1
            if p:
                lint_pho(uid, t, p)
                if uid in pho:
                    new_pho.append((uid, p))
                out.append((tib, p, cz)); prov['bank' if key in bank else 'pho_done'] += 1
            else:
                missing_pho.append((uid, tib))
                out.append((tib, 'PHO?', cz)); prov['missing'] += 1
        else:
            out.append((tib, None, cz)); prov['base' if not cz_override else 'override'] += 1

    if bank:
        token_check(new_pho, bank)

    if (missing_pho or missing_mantra) and not args.allow_gaps:
        d = Path(args.source).parent
        if missing_pho:
            (d / 'pho_todo.txt').write_text(
                ''.join(f'{n}\t{t}\n' for n, t in missing_pho), encoding='utf-8')
        if missing_mantra:
            (d / 'mantra_todo.txt').write_text(
                ''.join(f'{n}\t{t}\n' for n, t in missing_mantra), encoding='utf-8')
        print(f'chybí fonetika: {len(missing_pho)} veršů, {len(missing_mantra)} manter '
              f'→ {d}/pho_todo.txt, mantra_todo.txt', file=sys.stderr)
        finish('build', exit_on_error=False)
        sys.exit(2)

    # --- fatální invarianty
    seen = {uid.split('.')[0] for uid, *_ in units}
    for num in src:
        if num not in seen:
            err('build', f'segment {num} nepřispěl do výstupu')
    recon = norm_tib(''.join(u[0] for u in out))
    if recon != norm_tib(''.join(src[n].tib for n in sorted(src, key=lambda x: float(x)))):
        err('build', 'rekonstrukce source ↔ výstup selhala')
    for tib, p, cz in out:
        for line in (p, cz):
            if line and has_tib(line):
                err('build', f'tibetský znak v netibetském řádku: {line[:50]!r}')

    if args.dry_run:
        print('provenience: ' + ', '.join(f'{k} {v}' for k, v in sorted(prov.items())))
        return finish('build')

    body = []
    if args.front:
        body.append(Path(args.front).read_text(encoding='utf-8').rstrip('\n'))
        body.append('')
    for tib, p, cz in out:
        body.append(tib)
        if p:
            body.append(p)
        body.append(cz)
        body.append('')
    if args.back:
        body.append(Path(args.back).read_text(encoding='utf-8').rstrip('\n'))
    Path(args.out).write_text('\n'.join(body) + '\n', encoding='utf-8')
    print(f'{args.out}: {len(out)} jednotek — '
          + ', '.join(f'{k} {v}' for k, v in sorted(prov.items())))
    return finish('build')


# ------------------------------------------------------------- 4. concord

def iter_texts(root, pattern):
    """Texty v jakékoli hloubce pod root (pattern s `**`); label = složka textu."""
    for p in sorted(Path(root).glob(pattern)):
        parts = p.relative_to(root).parts
        cycle = parts[0] if len(parts) > 1 else '.'
        text = parts[-2] if len(parts) > 1 else p.stem
        yield cycle, text, p


def cmd_concord(args):
    root = Path(args.root)
    term = args.term
    tkey = key_tib(term)
    total = 0

    if not args.originals_only:
        print(f'=== hotové překlady (jak už bylo přeloženo)')
        for cycle, text, p in iter_texts(root, '**/text.md'):
            lines = p.read_text(encoding='utf-8').split('\n')
            shown = 0
            for i, l in enumerate(lines):
                if not has_tib(l) or tkey not in key_tib(l):
                    continue
                if shown >= args.max:
                    break
                cz = next((x for x in lines[i + 1:i + 3]
                           if x.strip() and not has_tib(x) and not looks_like_pho(x)), '')
                print(f'  [{cycle} / {text[:44]}]')
                print(f'    tib: {l.strip()[:120]}')
                if cz:
                    print(f'    cz : {cz.strip()[:120]}')
                shown += 1
                total += 1

    if not args.translated_only:
        print(f'=== originály (kontext ±{args.context})')
        for cycle, text, p in iter_texts(root, '**/original.md'):
            body = p.read_text(encoding='utf-8')
            hits = [m.start() for m in re.finditer(re.escape(term), body)]
            if not hits:
                continue
            print(f'  [{cycle} / {text[:44]}]  {len(hits)}×')
            for off in hits[:args.max]:
                a = max(0, off - args.context)
                b = min(len(body), off + len(term) + args.context)
                snip = re.sub(r'\s+', ' ', body[a:off]) + ' «' + term + '» ' \
                       + re.sub(r'\s+', ' ', body[off + len(term):b])
                print(f'    …{snip}…')
            total += len(hits)

    print(f'celkem {total} výskytů', file=sys.stderr)
    return finish('concord', exit_on_error=False)


# ------------------------------------------- 4b. česká konkordance ve vzorech

DEFAULT_REF = '/Users/prokop/texts/reference/mined'


def load_ref_lines(ref_dir, pho_only=False):
    """Řádky vytěžených vzorových brožur; pho_only = jen fonetické řádky.

    Rozlišení je nutné: prostý grep přes celý soubor počítá i česká jména
    v poznámkách, takže fonetický token vypadá doloženěji, než je.
    """
    out = []
    for p in sorted(Path(ref_dir).glob('*.txt')):
        for l in p.read_text(encoding='utf-8', errors='replace').split('\n'):
            if not l.strip():
                continue
            if pho_only and not looks_like_pho(l):
                continue
            out.append(l)
    return out


def word_re(needle, prefix=False):
    """Hranice slova na obou stranách (prefix=True jen na začátku), case-insensitive.

    Tohle je celý smysl modulu: `grep trvalost` najde i „vytrvalost" a přesně tak
    se do glosáře dostal nedoložený tvar. `(?<![^\\W\\d_])` drží levou hranici i pro
    česká písmena s diakritikou.
    """
    esc = re.escape(needle)
    tail = '' if prefix else r'(?!\w)'
    return re.compile(r'(?<!\w)' + esc + tail, re.IGNORECASE | re.UNICODE)


def count_in(needle, lines, prefix=False):
    rx = word_re(needle, prefix)
    return sum(len(rx.findall(l)) for l in lines)


def cmd_cz(args):
    lines = load_ref_lines(args.ref, pho_only=args.pho)
    term = args.term
    whole = count_in(term, lines)
    pref = count_in(term, lines, prefix=True)
    sub = sum(l.lower().count(term.lower()) for l in lines)

    scope = 'fonetické řádky' if args.pho else 'všechny řádky'
    print(f'„{term}" ve vzorech ({scope}):')
    print(f'  celé slovo      {whole}×')
    if args.pho:
        # Fonetické tokeny se neskloňují, takže předponový počet jen sbírá cizí
        # slova (THRI by „doložilo" THRIN z phrin las). Rozhoduje celé slovo.
        print(f'  jako podřetězec {sub}×   (předpona se u fonetiky neposuzuje)')
    else:
        print(f'  jako předpona   {pref}×   (celé slovo + skloňované tvary)')
        print(f'  jako podřetězec {sub}×')

    base = whole if args.pho else pref
    if sub > base:
        rx = re.compile(r'\w*' + re.escape(term) + r'\w*', re.IGNORECASE | re.UNICODE)
        hosts = Counter(m.group(0).lower() for l in lines for m in rx.finditer(l))
        inside = {w: n for w, n in hosts.items() if not word_re(term, True).fullmatch(w)}
        if inside:
            warn('cz', f'{sub - base} výskytů je jen UVNITŘ jiných slov: '
                       + ', '.join(f'{w} {n}×' for w, n in
                                   Counter(inside).most_common(5)))
    if base == 0:
        warn('cz', 'žádný doklad jako samostatné slovo — u česky znějícího termínu '
                   'je to varovný signál, ne povolení')

    shown = 0
    rx = word_re(term, prefix=not args.pho)
    for l in lines:
        if shown >= args.max or not rx.search(l):
            continue
        print(f'    {l.strip()[:150]}')
        shown += 1
    return finish('cz', exit_on_error=False)


# ---------------------------------------------------------- 5. glossary

GLOSS_COLS = ('tib', 'wylie', 'czech', 'stem', 'status', 'note')


def load_glossary(path):
    rows = []
    for raw in Path(path).read_text(encoding='utf-8').splitlines():
        if not raw.strip() or raw.lstrip().startswith('#'):
            continue
        f = raw.split('\t')
        f += [''] * (len(GLOSS_COLS) - len(f))
        row = dict(zip(GLOSS_COLS, f[:len(GLOSS_COLS)]))
        row['status'] = row['status'].strip() or 'prov'
        row['stem'] = row['stem'].strip() or row['czech'].strip()[:-2]
        rows.append(row)
    return rows


DEFAULT_GLOSSARY = str(Path(__file__).resolve().parent.parent / 'glossary.tsv')


def glossary_drift(rows, lines):
    """[(row, počet výskytů, [(řádek, česká glosa)])] pro segmenty s odchylkou."""
    out = []
    for r in rows:
        tkey, stem = key_tib(r['tib']), fold(r['stem'])
        if not tkey or not stem:
            continue
        hits, bad = 0, []
        for i in range(front_matter_end(lines), len(lines)):
            l = lines[i]
            if not has_tib(l) or tkey not in key_tib(l):
                continue
            czs = czech_lines(lines, i)
            if not czs:
                continue                          # mantra bez české glosy
            hits += 1
            if not any(stem in fold(c) for c in czs):
                bad.append((i + 1, ' / '.join(czs).strip()))
        out.append((r, hits, bad))
    return out


def cmd_glossary(args):
    gpath = Path(args.file) if args.file else Path(DEFAULT_GLOSSARY)
    if args.check and not args.corpus:
        err('glossary', '--check vyžaduje --corpus')
        return finish('glossary')
    corpus = Path(args.corpus) if args.corpus else None

    rows = load_glossary(gpath)

    if args.prompt:
        print('Ustanovené konvence (závazné, generováno z glossary.tsv):')
        for r in rows:
            if r['status'] == 'open':
                continue
            mark = '' if r['status'] == 'fixed' else ' (provizorní)'
            note = f" — {r['note']}" if r['note'].strip() else ''
            print(f"- {r['wylie'] or r['tib']} = {r['czech']}{mark}{note}")
        return 0

    if args.check:
        fixed = [r for r in rows if r['status'] == 'fixed']
        print(f'# glossary --check: {len(fixed)} závazných termínů')
        stat = {id(r): [0, []] for r in fixed}
        for _, text, p in iter_texts(corpus, '**/text.md'):
            lines = p.read_text(encoding='utf-8').split('\n')
            for r, hits, bad in glossary_drift(fixed, lines):
                s = stat[id(r)]
                s[0] += hits
                s[1] += [(text[:38], ln, cz[:70]) for ln, cz in bad]
        for r in fixed:
            hits, bad = stat[id(r)]
            label = (r['wylie'] or r['tib']) + ' → ' + r['czech']
            if bad:
                warn('glossary', f'{label}: {len(bad)} z {hits} výskytů jinak')
                for text, ln, cz in bad[:args.max]:
                    print(f'    {text}:{ln}  {cz}')
            else:
                print(f'  ok  {label}  ({hits}×)')
        return finish('glossary', exit_on_error=False)

    if args.audit:
        # Opačný směr než --check: ten hlídá text proti glosáři, tohle glosář proti
        # vzorům. Šest vad cyklu Pudri Rekpung (Džigdral, vidjádhara, vítězové,
        # samaji a dva neinvariantní stemy) prošlo celým prvním během právě proto,
        # že tuhle kontrolu nikdo neudělal.
        lines = load_ref_lines(args.ref)
        report = []
        for r in rows:
            if r['status'] == 'open':
                continue
            stem, czech = r['stem'].strip(), r['czech'].strip()
            if not stem:
                continue
            pref = count_in(stem, lines, prefix=True)
            sub = sum(l.lower().count(stem.lower()) for l in lines)
            # Stem nemusí být předpona celé fráze: hlavička glosáře u víceslovných
            # termínů žádá ROZLIŠUJÍCÍ slovo („z lebek", „bez počátku"). Vadou je
            # teprve stem, který v českém poli vůbec není.
            bad_stem = fold(stem) not in fold(czech)
            report.append((pref, sub, bad_stem, r))

        report.sort(key=lambda x: (x[0], x[1]))
        print(f'# glossary --audit: {len(report)} termínů proti {args.ref}')
        for pref, sub, bad_stem, r in report:
            label = f"{r['wylie'] or r['tib']} → {r['czech']}"
            flag = ''
            if bad_stem:
                flag += ' STEM-NENÍ-PREFIX'
            if pref == 0 and sub > 0:
                flag += ' JEN-UVNITŘ-JINÝCH-SLOV'
            if pref == 0 and r['status'] == 'fixed':
                warn('glossary', f'{label}: stem „{r["stem"]}" 0× ve vzorech{flag}')
            elif pref == 0:
                print(f'  --  {label}: 0× (prov, oporu nevyžaduje){flag}')
            elif pref < 3 and r['status'] == 'fixed':
                warn('glossary', f'{label}: stem „{r["stem"]}" jen {pref}× — '
                                 f'na `fixed` je to slabá opora{flag}')
            else:
                print(f'  ok  {label}  ({pref}×){flag}')
        return finish('glossary', exit_on_error=False)

    print(f'{gpath}: {len(rows)} řádků '
          + ', '.join(f'{k} {v}' for k, v in Counter(r['status'] for r in rows).items()))
    return 0


# ---------------------------------------------------- 6. pho (z lexikonu)

DEFAULT_LEXICON = '/Users/prokop/texts/reference/mined/pho_lexicon.tsv'


def tib_syllables(line):
    """Slabiky tibetského řádku (bez interpunkce a značek); `ཿ` dělí, viz syl()."""
    core = re.sub(f'[^{TIB}]', ' ', line)
    core = re.sub(f'[{SHAD}{NYIS_SHAD}{SBRUL_SHAD}{TERMA_SHAD}༄༅༃]', ' ', core)
    core = re.sub(f'{VISARGA}(?=[^{TSHEG}\\s])', VISARGA + TSHEG, core)
    return [s for s in re.split(f'[{TSHEG}\\s]+', core) if s]


def load_lexicon(path):
    """slabika → (dominantní přepis, jistota 0–1). Zdroj: pdfmine lexicon."""
    lex = {}
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        if line.startswith('#') or not line.strip():
            continue
        f = line.split('\t')
        if len(f) < 3 or not f[2].isdigit():
            continue
        top, n = f[1], int(f[2])
        total = n
        for v in (f[3] if len(f) > 3 else '').split(' | '):
            m = re.match(r'.+ (\d+)×$', v.strip())
            if m:
                total += int(m.group(1))
        lex[f[0]] = (top, n / max(total, 1), n)
    return lex


def render_pho(tib, lex, singletons=None):
    """→ (fonetika, neznámé slabiky). Neznámá slabika se značí ???.

    `singletons` (list) posbírá slabiky, jejichž přepis stojí na JEDINÉM zarovnání.
    Takový záznam dostane v `load_lexicon` spolehlivost 1,0, i když je to klidně
    misalignment: `སརྦ → TRI` z jedné stránky vyrobil „TRI VIGHNĀN BAM" místo
    „SARVA BIGHNAN BAM". 444 z 1254 záznamů lexikonu stojí na jednom výskytu, takže
    je nelze zahodit — ale revidující musí vědět, kde se dívat.
    """
    out, unknown = [], []
    for s in tib_syllables(tib):
        if s in lex:
            out.append(lex[s][0])
            if singletons is not None and len(lex[s]) > 2 and lex[s][2] <= 1:
                singletons.append((s, lex[s][0]))
        else:
            out.append('???')
            unknown.append(s)
    return ' '.join(out), unknown


MERGE_MIN = 2      # slitý tvar s jediným výskytem není doklad, ale šum


def merge_bigrams(pho, ref_lines, log=None, thin=None):
    """Slije sousední tokeny tam, kde vzory slitý tvar píší častěji než rozdělený.

    Lexikon je slabikový, takže slité tvary (JEŠE, SÖLWA, LAMA, HERUKA…) vyrobit
    nedokáže a `render_pho` je vždy rozdělí. Test je čisté počítání, proto patří sem
    a ne do agenta — dřív ho dělal subagent po jednotlivých grepech za ~150 k tokenů
    na text.

    Dvě věci, které tenhle test principiálně nechytá (a nepředstírá to):
    vsunuté `n` (KHA + DRO → KHANDRO) a trojslabičné složeniny.
    """
    toks = pho.split()
    i = 0
    while i < len(toks) - 1:
        a, b = toks[i], toks[i + 1]
        if '???' in (a, b):
            i += 1
            continue
        split_n = count_in(f'{a} {b}', ref_lines)
        merged_n = count_in(f'{a}{b}', ref_lines)
        if merged_n > split_n and merged_n >= MERGE_MIN:
            toks[i:i + 2] = [a + b]
            if log is not None:
                log.append((f'{a} {b}', split_n, a + b, merged_n))
            continue                       # týž index znovu — může jít slít i dál
        if merged_n > split_n and thin is not None:
            # Slitý tvar sice vyhrál, ale na jednom výskytu. Nesléváme a hlásíme —
            # tohle je přesně místo, kde subagent dřív uplatnil soud nad kontextem.
            thin.append((f'{a} {b}', split_n, a + b, merged_n))
        i += 1
    return ' '.join(toks)


def cmd_pho(args):
    lex = load_lexicon(args.lexicon)
    src = parse_source(args.source)
    ref_lines = [] if args.no_merge else load_ref_lines(args.ref, pho_only=True)
    merges, thin, weak_lex = [], [], []
    done, todo = [], []
    for num in sorted(src, key=lambda x: float(x)):
        seg = src[num]
        if seg.type not in ('verse', 'mantra'):
            continue
        singles = []
        pho, unknown = render_pho(seg.tib, lex, singles)
        if unknown:
            todo.append((num, seg.tib, unknown))
        else:
            weak_lex += [(num, syl_, tr) for syl_, tr in singles]
            if ref_lines:
                log, weak = [], []
                pho = merge_bigrams(pho, ref_lines, log, weak)
                merges += [(num, *m) for m in log]
                thin += [(num, *m) for m in weak]
            done.append((num, pho))
    out = Path(args.out)
    out.write_text(''.join(f'{n}\t{p}\n' for n, p in done), encoding='utf-8')
    todo_path = Path(args.todo) if args.todo else out.parent / 'pho_todo.txt'
    if todo:
        todo_path.write_text(
            ''.join(f'{n}\t{t}\t# neznámé: {" ".join(u)}\n' for n, t, u in todo),
            encoding='utf-8')
    total = len(done) + len(todo)
    print(f'{out}: {len(done)}/{total} veršů z lexikonu '
          f'({len(done)/max(total,1):.0%})')
    if merges:
        print(f'sloučeno dle vzorů: {len(merges)}×')
        for num, pair, sn, joined, mn in merges:
            print(f'  {num}: {pair} ({sn}×) → {joined} ({mn}×)')
    if weak_lex:
        uniq = {(sy, tr) for _, sy, tr in weak_lex}
        warn('pho', f'{len(uniq)} slabik stojí na JEDINÉM zarovnání lexikonu — '
                    f'ověř je (`cz <TOKEN> --pho`), tady vznikají misalignmenty')
        for sy, tr in sorted(uniq):
            segs = sorted({n for n, s2, _ in weak_lex if s2 == sy}, key=float)
            print(f'  {sy} → {tr}   segmenty: {", ".join(map(str, segs[:8]))}')
    if thin:
        print(f'NESLOUČENO, slabý doklad (slitý tvar < {MERGE_MIN}×): {len(thin)}× '
              f'— rozhodni ručně podle kontextu')
        for num, pair, sn, joined, mn in thin:
            print(f'  {num}: {pair} ({sn}×) vs {joined} ({mn}×)')
    if todo:
        miss = Counter(s for _, _, u in todo for s in u)
        print(f'{todo_path}: {len(todo)} veršů s neznámou slabikou; '
              f'nejčastější: {", ".join(s for s, _ in miss.most_common(6))}')
    return finish('pho', exit_on_error=False)


# ------------------------------------------------------------- 7. meter

CZ_VOWELS = 'aáeéěiíoóuúůyý'
# Naměřeno na 1683 verších vzorových textů v reference/ (25 brožur, 2026-07): české
# slabiky dělené tibetskými. Vzory jsou autorita — jejich úzus je expanzivnější než
# dřívější norma skillu (1,71×), protože nesou vysvětlující vsuvky v závorkách.
MEDIAN_EXPANSION = 2.33
OUTLIER_EXPANSION = 4.33


def cz_syl(line):
    """České slabiky ≈ skupiny samohlásek; ou/au/eu jako jedna."""
    s = re.sub(r'[^\w\s]', ' ', line.lower())
    s = re.sub(r'(ou|au|eu)', 'ó', s)
    return len(re.findall(f'[{CZ_VOWELS}]+', s))


def verse_triplets(lines):
    """(index, tib, pho, cz) pro trojice verš/mantra; rubriky a front matter mimo."""
    out = []
    i = front_matter_end(lines)
    while i < len(lines) - 2:
        if has_tib(lines[i]) and looks_like_pho(lines[i + 1]) and lines[i + 2].strip() \
                and not has_tib(lines[i + 2]):
            out.append((i + 1, lines[i], lines[i + 1], lines[i + 2]))
            i += 3
        else:
            i += 1
    return out


def cmd_meter(args):
    """Recitovatelnost se měří RELATIVNÍ expanzí, ne absolutním rozdílem slabik.

    Čeština je polysylabická a flektivní: sedmislabičný tibetský verš věrně
    přeložený zabere ~12 slabik. Naměřeno na 1127 verších cyklu Pudri Rekpung:
    medián 1.71×, p90 2.43×, p99 3.00× (MEDIAN_EXPANSION/OUTLIER níže). Absolutní
    limit („±3 slabiky") by tlačil k telegrafické češtině — proto se hlídá jen
    odlehlost vůči tomuto pásmu.
    """
    lines = Path(args.text).read_text(encoding='utf-8').split('\n')
    rows = []
    for ln, tib, pho, cz in verse_triplets(lines):
        t, c = syl(tib), cz_syl(cz)
        if t >= 4 and c:
            rows.append((c / t, ln, t, c, cz.strip()))
    if not rows:
        print('žádné verše k měření')
        return 0
    ratios = sorted(r[0] for r in rows)
    n = len(ratios)
    print(f'{args.text}: {n} veršů | expanze medián {ratios[n // 2]:.2f}×, '
          f'p10 {ratios[int(n * .1)]:.2f}×, p90 {ratios[int(n * .9)]:.2f}× '
          f'(korpus: {MEDIAN_EXPANSION:.2f}× / p99 {OUTLIER_EXPANSION:.2f}×)')
    over = [r for r in rows if r[0] > args.max_ratio]
    print(f'nad {args.max_ratio:.2f}× (kandidáti revize): {len(over)} ({len(over) / n:.0%})')
    for ratio, ln, t, c, cz in sorted(over, reverse=True)[:args.max]:
        print(f'  ř.{ln:>5}  tib {t:>2} / cz {c:>2} ({ratio:.2f}×)  {cz[:80]}')
    return 0


# ----------------------------------------------------------- 6b. czech (export)

def czech_line_numbers(lines):
    """[(číslo řádku v text.md, český řádek)] pro celý text bez titulního bloku.

    Prázdný řádek předává jako (0, '') — hranice strof musí korektor vidět, jinak
    nemůže soudit pravidlo „neopakuj totéž slovo ve dvou sousedních řádcích".

    Fonetika se pozná **pozicí v bloku, ne stylem řádku** — `looks_like_pho` bere za
    fonetiku i český verš minuskami bez interpunkce („kéž se jejich klam rozplyne"),
    takže stylový filtr by takové verše z exportu tiše vypustil (viz czech_lines).
    """
    out = []
    i = front_matter_end(lines)
    while i < len(lines):
        l = lines[i]
        if not l.strip():
            out.append((0, ''))
            i += 1
        elif has_tib(l):
            raw = []
            for nxt in lines[i + 1:i + 5]:
                if not nxt.strip() or has_tib(nxt):
                    break
                raw.append(nxt)
            cz = czech_lines(lines, i)
            off = len(raw) - len(cz)           # fonetika/titul na začátku bloku
            for k, c in enumerate(cz):
                out.append((i + off + k + 2, c))
            i += 1 + len(raw)
        else:
            out.append((i + 1, l))             # rubrika/nadpis/kolofon bez tibetštiny
            i += 1
    return out


def cmd_czech(args):
    """Jen české řádky text.md, očíslované — vstup pro monolingválního korektora.

    Korektor nesmí vidět tibetštinu ani fonetiku: s originálem po ruce si nečeskou
    formulaci omluví zdrojem („ale tibetsky to tak stojí"), a to je přesně vada,
    kterou má najít. Čísla řádků jsou čísla řádků text.md, aby findingy šly citovat
    stejným adresováním jako `check` a `meter`.
    """
    lines = Path(args.text).read_text(encoding='utf-8').split('\n')
    rows = czech_line_numbers(lines)
    for n, cz in rows:
        print(f'{n}\t{cz}' if cz else '')
    n_cz = sum(1 for _, cz in rows if cz)
    print(f'{args.text}: {n_cz} českých řádků', file=sys.stderr)
    return 0


# ----------------------------------------------------------------- 7. check

def cmd_check(args):
    lines = Path(args.text).read_text(encoding='utf-8').split('\n')

    if args.original:
        original = norm_tib(Path(args.original).read_text(encoding='utf-8'))
        got = norm_tib(''.join(l for l in lines if has_tib(l)))
        sm = difflib.SequenceMatcher(None, original, got, autojunk=False)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag in ('delete', 'replace') and (i2 - i1) >= 8:
                err('check', f'chybí/změněno {i2-i1} znaků originálu na offsetu {i1}: '
                             f'…{original[i1:i1+60]}…')

    fm_end = front_matter_end(lines)

    for i, l in enumerate(lines):
        if not l.strip():
            continue
        if is_punct_only(l):
            err('check', f'{i+1}: řádek obsahuje jen tibetskou interpunkci: {l!r}')
        if 'PHO?' in l or 'TODO' in l:
            err('check', f'{i+1}: placeholder v textu: {l.strip()[:50]}')
        if has_tib(l) and i >= fm_end:
            nxt = lines[i + 1] if i + 1 < len(lines) else ''
            if not nxt.strip() or has_tib(nxt):
                err('check', f'{i+1}: osiřelý tibetský řádek: {l[:50]}')
        if not has_tib(l) and re.search(f'[{TIB}]', l):
            err('check', f'{i+1}: tibetský znak v českém řádku')

    # varování: fonetika vs. slabiky
    for i in range(len(lines) - 1):
        if has_tib(lines[i]) and looks_like_pho(lines[i + 1]):
            a, b = syl(lines[i]), len(pho_tokens(lines[i + 1]))
            if b and abs(a - b) > 2:
                warn('check', f'{i+2}: fonetika má {b} slov, tibetština {a} slabik '
                              f'— možná posunutá: {lines[i+1][:40]}')

    # varování: recitovatelnost — relativní expanze nad p99 korpusu (~1 % řádků)
    max_ratio = getattr(args, 'max_ratio', OUTLIER_EXPANSION)
    for ln, tib, pho, cz in verse_triplets(lines):
        t, c = syl(tib), cz_syl(cz)
        if t >= 4 and c and c / t > max_ratio:
            warn('check', f'{ln+2}: {c} českých slabik na {t} tibetských '
                          f'({c/t:.2f}× proti mediánu {MEDIAN_EXPANSION:.2f}×) '
                          f'— pravděpodobně výklad ve verši: {cz.strip()[:60]}')
    # varování: drift proti glosáři — jediná pojistka proti tomu, aby banka tripletů
    # a --reuse vtáhly termín, který glosář už zamítl (viz sekce Terminologie v SKILL.md)
    for r, _, bad in glossary_drift([g for g in load_glossary(DEFAULT_GLOSSARY)
                                     if g['status'] == 'fixed'], lines):
        for ln, cz in bad[:3]:
            warn('check', f'{ln}: glosář žádá „{r["czech"]}" pro '
                          f'{r["wylie"] or r["tib"]}: {cz[:60]}')

    print(f'{args.text}: zkontrolováno {len(lines)} řádků')
    return finish('check')


# -------------------------------------------------------------- 5. selftest

FIXTURE_TERMA = (
    '༄༅། །རྡོ་རྗེ་ཕུར་པའི་ལས་བྱང་བཞུགས་སོ། །\n\n'
    'ཧཱུྃ༔ རྡོ་རྗེ་ཁྲོས་པས་ཞེ་སྡང་གཅོད༔ མཚོན་ཆེན་སྔོན་པོ་འབར་བ་ཡིས༔ '
    'ཨོཾ་བཛྲ་ཀཱི་ལི་ཀཱི་ལ་ཡ་ཧཱུྃ་ཕཊ༔ '
    'ཞེས་བཟླས་པ་བྱ། ཐུན་གྱི་མཐར།༔ '
    '།༎'
)
FIXTURE_SHAD = (
    '༄༅། །གཏོར་མའི་དཔེའུ་རིས་བཞུགས། ། '
    '༈ རྩ་གཏོར་གྲུ་བཞི་པའོ། ༈ ཆད་མདོ་སྤྱི་ལྟར།'
)


def cmd_consist(args):
    """Týž tibetský řádek → táž čeština napříč hotovými texty cyklu.

    `glossary --check` je per-text a per-termín; tohle hlídá celé řádky. Přesně to má
    zajišťovat banka tripletů, ale banka se uplatní jen při buildu — text sestavený
    dřív, než sourozenec existoval, o ní neví.
    """
    seen = {}          # key_tib -> {čeština: [texty]}
    for _, text, p in iter_texts(args.corpus, '**/text.md'):
        lines = p.read_text(encoding='utf-8').split('\n')
        for i in range(front_matter_end(lines), len(lines)):
            if not has_tib(lines[i]):
                continue
            czs = czech_lines(lines, i)
            if not czs:
                continue
            cz = ' / '.join(c.strip() for c in czs)
            key = key_tib(lines[i])
            if len(key) < 8:                 # krátké řádky (mantry, značky) nesoudíme
                continue
            seen.setdefault(key, {}).setdefault(cz, []).append(text[:38])

    clashes = {k: v for k, v in seen.items() if len(v) > 1}
    shared = sum(1 for v in seen.values() if sum(len(t) for t in v.values()) > 1)
    print(f'# consist: {len(seen)} unikátních tibetských řádků, '
          f'{shared} se opakuje napříč texty')
    for key, variants in sorted(clashes.items(), key=lambda x: -len(x[1]))[:args.max]:
        warn('consist', f'{len(variants)} různých překladů téhož řádku:')
        for cz, texts in variants.items():
            print(f'    [{", ".join(sorted(set(texts)))}] {cz[:110]}')
    if not clashes:
        print('  ok  žádný tibetský řádek nemá napříč texty dvě různé češtiny')
    return finish('consist', exit_on_error=False)


def cmd_selftest(_args):
    import tempfile
    ok = True
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        for name, text, mode in (('terma', FIXTURE_TERMA, 'terma'),
                                 ('shad', FIXTURE_SHAD, 'shad')):
            orig = td / f'{name}.md'
            orig.write_text(text, encoding='utf-8')
            out = td / f'{name}_source.md'
            ns = argparse.Namespace(original=str(orig), out=str(out), delim='auto', note=None)
            global _warn, _err
            _warn = _err = 0
            cmd_segment(ns)
            segs = parse_source(out)
            recon = norm_tib(''.join(s.tib for s in segs.values()))
            assert recon == norm_tib(text), f'{name}: rekonstrukce'
            assert all(not is_punct_only(s.tib) for s in segs.values()), f'{name}: punct-only'
            types = [s.type for s in sorted(segs.values(), key=lambda s: float(s.num))]
            print(f'selftest {name}: {len(segs)} segmentů, typy {types}')
            if name == 'terma':
                assert 'mantra' in types, 'mantra nedetekována'
                assert types[0] == 'heading', 'heading nedetekován'
            else:
                assert len(segs) >= 3, 'shad režim: ༈ nerozdělil jednotky'

    tib = 'ངོ་བོ་ཉིད།'
    assert czech_lines([tib, 'NGO WO ŇI', 'esence sama'], 0) == ['esence sama'], \
        'czech_lines: verš'
    assert czech_lines([tib, 'ngo wo ňi', 'esence sama'], 0) == ['esence sama'], \
        'czech_lines: verš se starou fonetikou minuskami'
    assert czech_lines([tib, 'OM AH HUNG'], 0) == [], 'czech_lines: mantra'
    assert czech_lines([tib, 'recitujte sedmkrát'], 0) == ['recitujte sedmkrát'], \
        'czech_lines: rubrika bez interpunkce'

    grow = [dict(tib='ངོ་བོ', wylie='ngo bo', czech='esence', stem='esenc',
                 status='fixed', note='')]
    assert not glossary_drift(grow, [tib, 'NGO WO ŇI', 'esence sama'])[0][2], \
        'glossary_drift: falešný poplach'
    assert glossary_drift(grow, [tib, 'NGO WO ŇI', 'podstata sama'])[0][2], \
        'glossary_drift: odchylka nezachycena'
    print('selftest czech_lines + glossary_drift: OK')

    doc = [tib, 'NGO WO ŇI', 'esence sama', '',
           tib, 'OM AH HUNG', '',
           tib, 'kéž se jejich klam rozplyne', '',
           'recitujte třikrát']
    got = [(n, c) for n, c in czech_line_numbers(doc) if c]
    assert got == [(3, 'esence sama'), (9, 'kéž se jejich klam rozplyne'),
                   (11, 'recitujte třikrát')], f'czech_line_numbers: {got}'
    assert all(doc[n - 1] == c for n, c in got), 'czech_line_numbers: čísla řádků'
    assert not any(has_tib(c) or looks_like_iast(c) for _, c in got), \
        'czech_line_numbers: tibetština v exportu'
    print('selftest czech_line_numbers: OK')

    # --- word_re / count_in: substringová past, kvůli které glosář nesl nedoložený tvar
    trap = ['a dosáhnou vytrvalosti', 'trvalost sama', 'TRVALOST']
    assert count_in('trvalost', trap) == 2, 'count_in: celé slovo'
    assert count_in('trvalost', trap, prefix=True) == 2, 'count_in: předpona'
    assert sum(l.lower().count('trvalost') for l in trap) == 3, 'count_in: podřetězec'
    assert count_in('řetězec', ['řetězců mantry'], prefix=True) == 0, \
        'count_in: „řetězec" není invariantní předpona tvaru „řetězců"'
    assert count_in('řetěz', ['řetězců mantry'], prefix=True) == 1, \
        'count_in: „řetěz" invariantní předpona je'
    print('selftest count_in (substringová past): OK')

    # --- merge_bigrams: slití jen tam, kde slitý tvar ve vzorech vyhrává počtem
    ref = ['JEŠE DOR DŽE SEM', 'JEŠE KJI ROL PA', 'JE ŠE SEM PA’I ŽÄL',
           'SÖLWA DEB SO', 'THÖ THRENG TSÄL PÄL', 'THÖ THRENG TSÄL DOR DŽE']
    assert merge_bigrams('JE ŠE KJI', ref) == 'JEŠE KJI', 'merge_bigrams: neslilo'
    assert merge_bigrams('THÖ THRENG TSÄL', ref) == 'THÖ THRENG TSÄL', \
        'merge_bigrams: slilo doloženou výjimku'
    assert merge_bigrams('??? ŠE', ref) == '??? ŠE', 'merge_bigrams: slilo ???'
    thin = []
    assert merge_bigrams('PHUR BU', ['PHURBU CHOG'], thin=thin) == 'PHUR BU', \
        'merge_bigrams: slilo na jediném výskytu'
    assert thin and thin[0][3] == 1, 'merge_bigrams: slabý doklad se nenahlásil'
    print('selftest merge_bigrams: OK')

    # --- render_pho hlásí slabiky z jediného zarovnání (zdroj misalignmentů)
    lex_ok = {'ངོ': ('NGO', 1.0, 12), 'བོ': ('WO', 1.0, 1)}
    sing = []
    got_pho, unk = render_pho('ངོ་བོ།', lex_ok, sing)
    assert got_pho == 'NGO WO', f'render_pho: {got_pho}'
    assert sing == [('བོ', 'WO')], f'render_pho: singleton nenahlášen ({sing})'
    assert not unk, 'render_pho: falešná neznámá slabika'
    print('selftest render_pho singletons: OK')

    # --- load_bank: vlastní složka se vynechává, jinak build čte svůj výstup
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        for name, cz in (('a', 'z textu A'), ('b', 'z textu B')):
            d = root / name
            d.mkdir()
            (d / 'text.md').write_text(f'{tib}\nNGO WO ŇI\n{cz}\n', encoding='utf-8')
        assert len(load_bank(root)) >= 1, 'load_bank: nic nenačetlo'
        both = load_bank(root)[key_tib(tib)][1]
        only_b = load_bank(root, exclude_dir=root / 'a')[key_tib(tib)][1]
        assert only_b == 'z textu B', f'load_bank: exclude_dir nefunguje ({only_b})'
        assert both in ('z textu A', 'z textu B'), 'load_bank: nečekaný obsah'
    print('selftest load_bank exclude_dir: OK')

    print('selftest OK' if ok else 'selftest FAILED')
    return 0


# ------------------------------------------------------------------- CLI

def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)

    p = sub.add_parser('segment')
    p.add_argument('original')
    p.add_argument('-o', '--out', required=True)
    p.add_argument('--delim', choices=['auto', 'terma', 'shad'], default='auto')
    p.add_argument('--note')
    p.set_defaults(fn=cmd_segment)

    p = sub.add_parser('compare')
    p.add_argument('--source', required=True)
    p.add_argument('--draft', action='append', required=True,
                   help='LABEL=cesta[,cesta2] (víc cest = dělený běh)')
    p.add_argument('-o', '--out')
    p.add_argument('--ratio', type=float, default=0.4)
    p.set_defaults(fn=cmd_compare)

    p = sub.add_parser('build')
    p.add_argument('--source', required=True)
    p.add_argument('--base', action='append', required=True)
    p.add_argument('--reuse')
    p.add_argument('--reuse-bank', help='triplet_bank.tsv ze vzorových textů')
    p.add_argument('--lexicon', default=DEFAULT_LEXICON)
    p.add_argument('--pho')
    p.add_argument('--mantra')
    p.add_argument('--overrides')
    p.add_argument('--front')
    p.add_argument('--back')
    p.add_argument('-o', '--out')
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--allow-gaps', action='store_true')
    p.set_defaults(fn=cmd_build)

    p = sub.add_parser('concord', help='KWIC přes originály i hotové překlady')
    p.add_argument('term')
    p.add_argument('--root', default='/Users/prokop/texts')
    p.add_argument('--context', type=int, default=60)
    p.add_argument('--max', type=int, default=25)
    g = p.add_mutually_exclusive_group()
    g.add_argument('--translated-only', action='store_true')
    g.add_argument('--originals-only', action='store_true')
    p.set_defaults(fn=cmd_concord)

    p = sub.add_parser('cz', help='doklad českého výrazu ve vzorech (celé slovo, ne podřetězec)')
    p.add_argument('term')
    p.add_argument('--ref', default=DEFAULT_REF)
    p.add_argument('--max', type=int, default=8)
    p.add_argument('--pho', action='store_true',
                   help='počítat jen na fonetických řádcích (pro fonetické tokeny)')
    p.set_defaults(fn=cmd_cz)

    p = sub.add_parser('glossary', help='globální glosář jako data')
    p.add_argument('--corpus', help='složka s texty k prověření driftu (--check)')
    p.add_argument('--file')
    p.add_argument('--ref', default=DEFAULT_REF, help='vytěžené vzory pro --audit')
    p.add_argument('--max', type=int, default=12)
    g = p.add_mutually_exclusive_group()
    g.add_argument('--prompt', action='store_true')
    g.add_argument('--check', action='store_true')
    g.add_argument('--audit', action='store_true',
                   help='opora glosáře ve vzorech: hlásí fixed termíny bez dokladu')
    p.set_defaults(fn=cmd_glossary)

    p = sub.add_parser('consist', help='týž tibetský řádek → táž čeština napříč texty')
    p.add_argument('--corpus', required=True)
    p.add_argument('--max', type=int, default=20)
    p.set_defaults(fn=cmd_consist)

    p = sub.add_parser('pho', help='fonetika z lexikonu vzorových textů')
    p.add_argument('--source', required=True)
    p.add_argument('--lexicon', default=DEFAULT_LEXICON)
    p.add_argument('--ref', default=DEFAULT_REF)
    p.add_argument('--no-merge', action='store_true',
                   help='vypnout slévání složenin dle bigramového testu')
    p.add_argument('-o', '--out', required=True)
    p.add_argument('--todo')
    p.set_defaults(fn=cmd_pho)

    p = sub.add_parser('meter', help='recitovatelnost: relativní expanze čeština/tibetština')
    p.add_argument('text')
    p.add_argument('--max-ratio', type=float, default=OUTLIER_EXPANSION)
    p.add_argument('--max', type=int, default=10)
    p.set_defaults(fn=cmd_meter)

    p = sub.add_parser('czech', help='jen české řádky, očíslované — pro korektora')
    p.add_argument('text')
    p.set_defaults(fn=cmd_czech)

    p = sub.add_parser('check')
    p.add_argument('text')
    p.add_argument('--source')
    p.add_argument('--original')
    p.add_argument('--max-ratio', type=float, default=OUTLIER_EXPANSION)
    p.set_defaults(fn=cmd_check)

    p = sub.add_parser('selftest')
    p.set_defaults(fn=cmd_selftest)

    args = ap.parse_args()
    if args.cmd == 'build' and not args.out and not args.dry_run:
        ap.error('build: -o/--out je povinné (nebo --dry-run)')
    sys.exit(args.fn(args) or 0)


if __name__ == '__main__':
    main()
