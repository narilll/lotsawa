#!/usr/bin/env python3
"""Mechanical steps of the lotsawa workflow: segmentation, draft comparison, assembly, lint.

Usage:
  lotsawa.py segment original.md -o drafts/source.md [--delim auto|terma|shad]
  lotsawa.py compare --source drafts/source.md --draft F=a.md[,b.md] --draft C=c.md
                     [-o drafts/review.md] [--ratio 0.4]
  lotsawa.py build --source drafts/source.md --base drafts/fable-tib.md [--base ...]
                   [--pho drafts/pho_done.txt] [--mantra drafts/mantra_done.txt]
                   [--overrides drafts/overrides.json] [--front f.txt] [--back b.txt]
                   -o text.md [--dry-run] [--allow-gaps] [--pho-lint]
                   # optional: [--reuse ../]  (sibling texts in the working folder)
  lotsawa.py check text.md [--source drafts/source.md] [--original original.md]
                   [--glossary TSV] [--max-ratio N]
  lotsawa.py glossary [--file TSV] [--prompt | --check --corpus DIR]
  lotsawa.py meter text.md [--max-ratio 4.56]
  lotsawa.py target text.md > drafts/target.txt   (alias: czech)
  lotsawa.py selftest

Data loss or corruption is fatal (exit 1); an editorial judgment call is a warning
(exit 0). Missing phonetics is a state, not an error: build writes *_todo.txt and
exits with 2.
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
SANSKRIT_MARKS = 'ཾཿཱྃྂ'          # ཾ ཿ ྃ ྂ ཱ
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
    """For reconstruction comparison: drops only whitespace, nothing else."""
    return re.sub(r'\s+', '', s)


# Orthographic variants of the same word across sources. Documented on the Seven-Line
# Prayer: published Czech translations write ཡུལ་གི and ཞེས་སུ་གགས, our source ཡུལ་གྱི and
# ཞེས་སུ་གྲགས, and the HUNG syllable carries ྂ / ྃ / ཾ depending on the typesetting.
# Only the bank key is folded — the translation, the phonetics, and the reconstruction
# check (norm_tib) never change.
KEY_EQUIV = [('གྱི', 'གི'), ('གྲགས', 'གགས'), ('ྂ', 'ྃ'), ('ཾ', 'ྃ'), ('ཿ', '')]


def key_tib(s):
    """Triplet-bank key: strips punctuation and tsheg, so སྟེང་༔ == སྟེང༔.

    Also normalizes the orthographic variants from KEY_EQUIV, otherwise the same
    verse from two booklets never matches.
    """
    s = re.sub(f'[\\s{TSHEG}{SHAD}{NYIS_SHAD}{SBRUL_SHAD}{TERMA_SHAD}༄༅༃]', '', s)
    for a, b in KEY_EQUIV:
        s = s.replace(a, b)
    return s


VISARGA = 'ཿ'          # rnam bcad — ends a syllable even without tsheg (ཨཱཿཧཱུྃ = 2 syllables)


def syl(s):
    """Syllable count: tsheg + 1 after stripping punctuation (0 for non-Tibetan text).

    `ཿ` counts as a divider: without this, ཨཱཿཧཱུྃ is one syllable, counts come out one
    too low, and the phonetics alignment silently shifts (in the Vajraguru mantra
    ཨོཾ་ཨཱཿཧཱུྃ་བཛྲ… this shifted the rest of the line).
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
    return [t for t in re.split(r'\W+', line.lower()) if t]


def looks_like_pho(line):
    """Phonetics line: uniform casing (UPPERCASE per published Czech translations, or
    lowercase in older ones) and no sentence-level punctuation.

    Published Czech translations write phonetics in uppercase, older skill output in lowercase —
    both must pass, otherwise everything resting on this predicate breaks
    (target_lines, verse_triplets, the bank, meter, check). Only a sentence is
    rejected, i.e. a line mixing upper- and lowercase the way target-language prose
    does.
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
    """Diacritic-stripped and lowercase — for comparing target-language word stems.

    Czech palatalizes (pohřebiště → pohřebišť), so the stem "pohřebišt" would not
    match the inflected form; after fold() both agree on "pohrebist".
    """
    nfd = unicodedata.normalize('NFD', s.lower())
    return ''.join(ch for ch in nfd if not unicodedata.combining(ch))


IAST_CHARS = 'ṃḥāīūṣṭḍñṛśḷṇ'


def looks_like_iast(line):
    return any(ch in IAST_CHARS for ch in line) or ' | ' in line


def target_lines(lines, i):
    """All target-language lines of the unit starting with the Tibetan line at index i.

    Returns [] for a mantra (the second line is phonetics, not target-language text).
    Returns more than one line for title blocks (title + author) and for rubrics with
    a multi-line translation — a term search must cover all of them, otherwise it
    misses matches.

    Phonetics is recognized **by position in the block, not by line style**: it sits
    right after the Tibetan. A style-only test isn't enough — `looks_like_pho` also
    treats an unpunctuated lowercase target-language verse ("kéž se jejich klam
    rozplyne") as phonetics, so a style filter over the whole block used to silently
    drop such verses, and the glossary check never saw them.
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
            unit = unit[1:]                # verse/title: phonetics (or title) comes first
        elif unit[0].strip() == unit[0].strip().upper():
            return []                      # mantra: Tibetan + phonetics in UPPERCASE
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
    """Tolerant parser: a header, then all non-blank lines joined with a space."""
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
                err('compare', f'segment {num} appears in two drafts ({origin[num]}, {p})')
            merged[num] = txt
            origin[num] = p
    return merged


# --------------------------------------------------------------- 1. segment

def split_units(text, mode):
    """Splits into units. Punctuation belongs to the preceding unit, ༈ to the following one."""
    if mode == 'terma':
        pat = f'(?<=[{TERMA_SHAD}])'
    else:
        # the boundary is after a whole run of shads (`། །`, `།།`, `༎`), including any spaces in it
        pat = f'(?<=[{SHAD}{NYIS_SHAD}])(?![\\s]*[{SHAD}{NYIS_SHAD}])'
    parts = [p for p in re.split(pat, text) if p.strip()]
    # ༈ and ༄ start a new unit
    out = []
    for p in parts:
        pieces = re.split(f'(?=[{SBRUL_SHAD}༄])', p)
        out.extend(x for x in pieces if x.strip())
    return merge_bare(out)


def merge_bare(units):
    """A unit without a Tibetan letter merges into the previous one; a leading ༄༅། ། merges into the next."""
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
    if pending:                      # the whole text has not a single Tibetan letter
        merged.append(pending)
    return [u.strip() for u in merged if u.strip()]


def split_intro(unit):
    """Second pass over a long block without ༔: verses split on shads, prose merged."""
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
    # merge adjacent prose; verses never
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
        warn('segment', f'last unit does not start with ཅེས/ཞེས — typing it as rubric, not colophon')
    inner = re.sub(f'[{SHAD}{NYIS_SHAD}\\s]+$', '', unit)
    if SHAD in inner:
        return 'rubric', False
    if n <= 9:
        return 'verse', False
    if n <= 14:
        return 'verse', True          # gray zone
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
            # merge punctuation remnants (a lone ༄༅། ། between the title and the body)
            kinds = {key_tib(p): k for k, p in pieces}
            for piece in merge_bare([p for _, p in pieces]):
                expanded.append((piece, kinds.get(key_tib(piece)) == 'verse'))
        else:
            expanded.append((u, None))

    segs, uncertain = [], []
    for i, (u, forced_verse) in enumerate(expanded):
        # tib: is a single-line field — internal breaks would be lost on write
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

    # --- fatal invariants
    recon = norm_tib(''.join(s.tib for s in segs))
    if recon != norm_tib(original):
        a, b = norm_tib(original), recon
        off = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
        err('segment', f'reconstruction failed at offset {off}\n'
                       f'  original: …{a[max(0,off-40):off+40]}…\n'
                       f'  segments: …{b[max(0,off-40):off+40]}…')
    for s in segs:
        if not s.tib.strip():
            err('segment', f'segment {s.num} is empty')
        if is_punct_only(s.tib):
            err('segment', f'segment {s.num} contains only punctuation: {s.tib!r}')
    if _err:
        finish('segment')

    if uncertain:
        warn('segment', f'uncertain type (gray zone 10–14 syllables) for segments: '
                        f'{", ".join(map(str, uncertain))}')

    note = args.note or f'auto-segmentation ({mode} mode), types are heuristic'
    lines = [f'# source — {note}', f'# {len(segs)} segments; suffix ? = uncertain type', '']
    for s in segs:
        lines.append(f'## {s.num} [{s.type}{"?" if s.uncertain else ""}]')
        lines.append(f'tib: {s.tib}')
        lines.append('')
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text('\n'.join(lines), encoding='utf-8')
    counts = Counter(s.type for s in segs)
    print(f'{args.out}: {len(segs)} segments ({mode}) — '
          + ', '.join(f'{k} {v}' for k, v in sorted(counts.items())))
    return finish('segment')


# --------------------------------------------------------------- 2. compare

def cmd_compare(args):
    src = parse_source(args.source)
    # split runs: --draft F=a.md --draft F=b.md (a comma won't do — folder names contain them)
    by_label = {}
    for spec in args.draft:
        label, _, path = spec.partition('=')
        by_label.setdefault(label, []).append(path)
    drafts = {label: merge_drafts(paths) for label, paths in by_label.items()}

    out = ['# compare']
    out.append('## coverage')
    for label, d in drafts.items():
        missing = sorted(set(src) - set(d), key=lambda x: float(x))
        extra = sorted(set(d) - set(src), key=lambda x: float(x))
        status = 'ok' if not missing and not extra else 'ERROR'
        out.append(f'{label} {len(d)}/{len(src)} {status}')
        if missing:
            err('compare', f'{label}: missing segments {missing[:20]}')
        if extra:
            err('compare', f'{label}: extra segments {extra[:20]}')

    out.append('## contamination with Tibetan punctuation in a target-language line')
    contam = {}
    for label, d in drafts.items():
        bad = [n for n, t in d.items() if has_tib(t)]
        contam[label] = len(bad) / max(len(d), 1)
        flag = '  -- DO NOT USE AS BASE' if contam[label] >= 0.10 else ''
        out.append(f'{label} {len(bad)}/{len(d)} segments ({contam[label]:.0%}){flag}')
        if bad:
            warn('compare', f'{label}: Tibetan punctuation in {len(bad)} target-language lines')
    base = min(contam, key=lambda k: contam[k]) if contam else '?'
    out.insert(1, f'base recommended: {base}')

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
        out.append(f'## needs review (ratio < {args.ratio:.2f})   {len(low)} segments')
        for n, r, ta, tb in low:
            out.append(f'{n}  {r:.2f}  [{src[n].type}] {src[n].tib[:60]}')
            out.append(f'  {a}: {ta[:200]}')
            out.append(f'  {b}: {tb[:200]}')
        disputed = sorted({n for n in src
                           if (drafts[a].get(n, '').strip() == '—')
                           != (drafts[b].get(n, '').strip() == '—')}, key=lambda x: float(x))
        out.append('## disputed mantras (one draft gave —, the other a translation)   '
                   + (' '.join(disputed) if disputed else '(none)'))
        if disputed:
            warn('compare', f'disputed mantras: {" ".join(disputed)}')

    text = '\n'.join(out) + '\n'
    if args.out:
        Path(args.out).write_text(text, encoding='utf-8')
        print(f'{args.out}: base={base}, needs review {len(low) if len(labels)>=2 else 0}')
    else:
        print(text)
    return finish('compare')


# ----------------------------------------------------------------- 3. build

def front_matter_end(lines):
    """Index past the title block: first run of ≥ 5 blank lines + the following title."""
    blanks = 0
    for i, l in enumerate(lines):
        blanks = blanks + 1 if not l.strip() else 0
        if blanks >= 5:
            return i + 6
    return 0


def load_bank(reuse_dir, exclude_dir=None):
    """key_tib(tib) -> (pho|None, target) from all sibling text.md files (title block excluded).

    `exclude_dir` skips one folder — typically the one currently being built. Without
    this, a second build reads its own previous output, and the bank (which takes
    precedence over both --pho and --base) silently discards a phonetics or base fix.
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
        targets = Counter(v[1] for v in vs)
        if len(targets) > 1:
            warn('build', f'bank: different translations of the same line — {list(targets)[:2]}')
        best = targets.most_common(1)[0][0]
        pho = next((v[0] for v in vs if v[0] and v[1] == best), None)
        bank[k] = (pho, best)
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
            err('build', f'{path}: line does not have {cols + 1} fields: {raw[:60]!r}')
            continue
        if cols == 1:
            out[parts[0]] = parts[1]
        else:
            out.setdefault(parts[0], {})[parts[1]] = parts[2]
    return out


def lint_pho(num, seg_type, pho, pho_lint=False):
    """Checks against the published-Czech-translations convention (see phonetics.md).

    Uppercase is a format requirement and always applies; the rest (length marks,
    PHET, TSH/CCH) are conventions of the specific (Czech) phonetics.md, so they only
    run behind --pho-lint.
    """
    letters = [ch for ch in pho if ch.isalpha()]
    if letters and any(ch.islower() for ch in letters):
        warn('build', f'seg {num}: phonetics must be UPPERCASE: {pho[:40]}')
    if not pho_lint:
        return
    if re.search(r'[áéíóúůý]', pho, re.I):
        warn('build', f'seg {num}: phonetics must carry no length marks (only Ä Ö Ü): {pho[:40]}')
    if re.search(r'\bPHE\b', pho, re.I):
        warn('build', f'seg {num}: ཕཊ must be transcribed PHET, not PHE')
    if re.search(r'\bCCH', pho, re.I):
        warn('build', f'seg {num}: the sibilant must be written TSH, not CCH: {pho[:40]}')


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
                warn('build', f'seg {num}: "{tok}" (new) vs '
                              + ', '.join(f'"{c}" ({corpus[c]}×)' for c in near))


def cmd_build(args):
    src = parse_source(args.source)
    base = merge_drafts(args.base)
    own = Path(args.out).resolve().parent if args.out else None
    bank = load_bank(args.reuse, exclude_dir=own) if args.reuse else {}
    pho = load_tsv(args.pho)
    mantra = load_tsv(args.mantra, cols=2)
    overrides = json.loads(Path(args.overrides).read_text(encoding='utf-8')) if args.overrides else {}

    # split segments into sub-units per overrides
    units = []      # (id, type, tib, target_or_None)
    for num in sorted(src, key=lambda x: float(x)):
        seg = src[num]
        if num in overrides:
            for j, (t, tib, cz) in enumerate(overrides[num], 1):
                units.append((f'{num}.{j}', t, tib, cz))
            covered = norm_tib(''.join(x[1] for x in overrides[num]))
            if covered != norm_tib(seg.tib):
                err('build', f'override of segment {num} does not cover the whole Tibetan content')
        else:
            units.append((num, seg.type, seg.tib, None))

    missing_pho, missing_mantra, out, prov, new_pho = [], [], [], Counter(), []
    for uid, t, tib, cz_override in units:
        key = key_tib(tib)
        if t == 'mantra':
            # Published Czech translations have a TWO-line mantra (Tibetan + phonetics), no IAST.
            m = mantra.get(uid)
            pho_m = (m or {}).get('pho')
            if not pho_m and key in bank and bank[key][0]:
                pho_m = bank[key][0]; prov['bank'] += 1
            elif pho_m:
                prov['mantra_done'] += 1
            if pho_m:
                lint_pho(uid, t, pho_m, args.pho_lint)
                out.append((tib, None, pho_m))
            else:
                missing_mantra.append((uid, tib))
                out.append((tib, None, 'PHO?')); prov['missing'] += 1
            continue
        cz = cz_override or (bank[key][1] if key in bank else base.get(uid, ''))
        if not cz:
            err('build', f'segment {uid} has no translation in any draft')
            cz = 'PHO?'
        cz = re.sub(f'[{TIB}]+', '', cz).strip() if has_tib(cz) else cz
        if t in ('verse',):
            p = (bank[key][0] if key in bank and bank[key][0] else pho.get(uid))
            if p:
                lint_pho(uid, t, p, args.pho_lint)
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
        print(f'missing phonetics: {len(missing_pho)} verses, {len(missing_mantra)} mantras '
              f'→ {d}/pho_todo.txt, mantra_todo.txt', file=sys.stderr)
        finish('build', exit_on_error=False)
        sys.exit(2)

    # --- fatal invariants
    seen = {uid.split('.')[0] for uid, *_ in units}
    for num in src:
        if num not in seen:
            err('build', f'segment {num} did not contribute to the output')
    recon = norm_tib(''.join(u[0] for u in out))
    if recon != norm_tib(''.join(src[n].tib for n in sorted(src, key=lambda x: float(x)))):
        err('build', 'source ↔ output reconstruction failed')
    for tib, p, cz in out:
        for line in (p, cz):
            if line and has_tib(line):
                err('build', f'Tibetan character in a non-Tibetan line: {line[:50]!r}')

    if args.dry_run:
        print('provenance: ' + ', '.join(f'{k} {v}' for k, v in sorted(prov.items())))
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
    print(f'{args.out}: {len(out)} units — '
          + ', '.join(f'{k} {v}' for k, v in sorted(prov.items())))
    return finish('build')


# ------------------------------------------------- 4. corpus helpers (working folder)

def iter_texts(root, pattern):
    """Texts at any depth under root (pattern with `**`); label = the text's folder."""
    for p in sorted(Path(root).glob(pattern)):
        parts = p.relative_to(root).parts
        cycle = parts[0] if len(parts) > 1 else '.'
        text = parts[-2] if len(parts) > 1 else p.stem
        yield cycle, text, p


# ---------------------------------------------------------- 5. glossary

GLOSS_COLS = ('tib', 'wylie', 'target', 'stem', 'status', 'note')


def default_glossary():
    """./glossary.tsv in the working directory if present, else the skill default."""
    local = Path('glossary.tsv')
    if local.is_file():
        return str(local)
    return str(Path(__file__).resolve().parent.parent / 'glossary.tsv')


def load_glossary(path):
    """empty stem = exact target string; inflecting languages should fill stem."""
    rows = []
    for raw in Path(path).read_text(encoding='utf-8').splitlines():
        if not raw.strip() or raw.lstrip().startswith('#'):
            continue
        f = raw.split('\t')
        f += [''] * (len(GLOSS_COLS) - len(f))
        row = dict(zip(GLOSS_COLS, f[:len(GLOSS_COLS)]))
        row['status'] = row['status'].strip() or 'prov'
        row['stem'] = row['stem'].strip() or row['target'].strip()
        rows.append(row)
    return rows


def glossary_drift(rows, lines):
    """[(row, hit count, [(line, target-language gloss)])] for segments with a drift."""
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
            czs = target_lines(lines, i)
            if not czs:
                continue                          # mantra without a target-language gloss
            hits += 1
            if not any(stem in fold(c) for c in czs):
                bad.append((i + 1, ' / '.join(czs).strip()))
        out.append((r, hits, bad))
    return out


def cmd_glossary(args):
    gpath = Path(args.file or default_glossary())
    print(f'note: glossary = {gpath}', file=sys.stderr)
    if args.check and not args.corpus:
        err('glossary', '--check requires --corpus')
        return finish('glossary')
    corpus = Path(args.corpus) if args.corpus else None

    rows = load_glossary(gpath)

    if args.prompt:
        print('Established conventions (binding, generated from glossary.tsv):')
        for r in rows:
            if r['status'] == 'open':
                continue
            mark = '' if r['status'] == 'fixed' else ' (provisional)'
            note = f" — {r['note']}" if r['note'].strip() else ''
            print(f"- {r['wylie'] or r['tib']} = {r['target']}{mark}{note}")
        return 0

    if args.check:
        fixed = [r for r in rows if r['status'] == 'fixed']
        print(f'# glossary --check: {len(fixed)} binding terms')
        stat = {id(r): [0, []] for r in fixed}
        for _, text, p in iter_texts(corpus, '**/text.md'):
            lines = p.read_text(encoding='utf-8').split('\n')
            for r, hits, bad in glossary_drift(fixed, lines):
                s = stat[id(r)]
                s[0] += hits
                s[1] += [(text[:38], ln, cz[:70]) for ln, cz in bad]
        for r in fixed:
            hits, bad = stat[id(r)]
            label = (r['wylie'] or r['tib']) + ' → ' + r['target']
            if bad:
                warn('glossary', f'{label}: {len(bad)} of {hits} occurrences differ')
                for text, ln, cz in bad[:args.max]:
                    print(f'    {text}:{ln}  {cz}')
            else:
                print(f'  ok  {label}  ({hits}×)')
        return finish('glossary', exit_on_error=False)

    print(f'{gpath}: {len(rows)} rows '
          + ', '.join(f'{k} {v}' for k, v in Counter(r['status'] for r in rows).items()))
    return 0


# ------------------------------------------------------------- 6. meter

# Measured on published Czech translations (1683 verses, 25 booklets, 2026-07). Only a
# starting point for another target language — recalibrate with `meter`; --max-ratio
# overrides both here.
MEDIAN_EXPANSION = 2.33
OUTLIER_EXPANSION = 4.33

# Latin-script targets only; vowels that do not NFD-decompose (ø, æ) and non-Latin
# scripts count 0 — extend per language.
VOWELS = 'aeiouy'


def target_syl(line):
    """Target-language syllables (Latin-script targets) ≈ vowel-run count after
    folding to plain lowercase."""
    return len(re.findall(f'[{VOWELS}]+', fold(line)))


def verse_triplets(lines):
    """(index, tib, pho, target) for verse/mantra triplets; rubrics and front matter excluded."""
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
    """Recitability is measured as RELATIVE expansion, not an absolute syllable difference.

    Czech is polysyllabic and inflectional: a seven-syllable Tibetan verse translated
    faithfully takes ~12 syllables. The thresholds MEDIAN_EXPANSION/OUTLIER_EXPANSION
    below were measured on published Czech translations and are only a starting point for another
    target language — override with --max-ratio, and recalibrate by running `meter`
    over your own finished texts. An absolute limit ("±3 syllables") would push
    toward telegraphic phrasing — so only the outlier distance from this band is
    flagged.
    """
    lines = Path(args.text).read_text(encoding='utf-8').split('\n')
    rows = []
    for ln, tib, pho, cz in verse_triplets(lines):
        t, c = syl(tib), target_syl(cz)
        if t >= 4 and c:
            rows.append((c / t, ln, t, c, cz.strip()))
    if not rows:
        print('no verses to measure')
        return 0
    ratios = sorted(r[0] for r in rows)
    n = len(ratios)
    print(f'{args.text}: {n} verses | expansion median {ratios[n // 2]:.2f}×, '
          f'p10 {ratios[int(n * .1)]:.2f}×, p90 {ratios[int(n * .9)]:.2f}× '
          f'(published Czech translations: {MEDIAN_EXPANSION:.2f}× / p99 {OUTLIER_EXPANSION:.2f}×)')
    over = [r for r in rows if r[0] > args.max_ratio]
    print(f'over {args.max_ratio:.2f}× (review candidates): {len(over)} ({len(over) / n:.0%})')
    for ratio, ln, t, c, cz in sorted(over, reverse=True)[:args.max]:
        print(f'  ln.{ln:>5}  tib {t:>2} / target {c:>2} ({ratio:.2f}×)  {cz[:80]}')
    return 0


# ------------------------------------------------------------ 7. target

def target_line_numbers(lines):
    """[(line number in text.md, target-language line)] for the whole text, title block excluded.

    Passes a blank line through as (0, '') — the proofreader must see stanza
    boundaries, otherwise they can't apply the rule "don't repeat the same word in
    two adjacent lines".

    Phonetics is recognized **by position in the block, not by line style** —
    `looks_like_pho` also treats an unpunctuated lowercase target-language verse
    ("kéž se jejich klam rozplyne") as phonetics, so a style filter would silently
    drop such verses from the export (see target_lines).
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
            cz = target_lines(lines, i)
            off = len(raw) - len(cz)           # phonetics/title at the start of the block
            for k, c in enumerate(cz):
                out.append((i + off + k + 2, c))
            i += 1 + len(raw)
        else:
            out.append((i + 1, l))             # rubric/heading/colophon without Tibetan
            i += 1
    return out


def cmd_target(args):
    """Only the target-language lines of text.md, numbered — input for a monolingual proofreader.

    The proofreader must not see the Tibetan or the phonetics: with the original at
    hand, an unnatural phrasing gets excused by the source ("but that's how it stands
    in Tibetan"), and that's exactly the defect they're supposed to catch. The line
    numbers are text.md line numbers, so findings can be cited with the same
    addressing as `check` and `meter`.
    """
    lines = Path(args.text).read_text(encoding='utf-8').split('\n')
    rows = target_line_numbers(lines)
    for n, cz in rows:
        print(f'{n}\t{cz}' if cz else '')
    n_cz = sum(1 for _, cz in rows if cz)
    print(f'{args.text}: {n_cz} target-language lines', file=sys.stderr)
    return 0


# ----------------------------------------------------------------- 8. check

def cmd_check(args):
    lines = Path(args.text).read_text(encoding='utf-8').split('\n')

    if args.original:
        original = norm_tib(Path(args.original).read_text(encoding='utf-8'))
        got = norm_tib(''.join(l for l in lines if has_tib(l)))
        sm = difflib.SequenceMatcher(None, original, got, autojunk=False)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag in ('delete', 'replace') and (i2 - i1) >= 8:
                err('check', f'missing/changed {i2-i1} characters of the original at offset {i1}: '
                             f'…{original[i1:i1+60]}…')

    fm_end = front_matter_end(lines)

    for i, l in enumerate(lines):
        if not l.strip():
            continue
        if is_punct_only(l):
            err('check', f'{i+1}: line contains only Tibetan punctuation: {l!r}')
        if 'PHO?' in l or 'TODO' in l:
            err('check', f'{i+1}: placeholder in the text: {l.strip()[:50]}')
        if has_tib(l) and i >= fm_end:
            nxt = lines[i + 1] if i + 1 < len(lines) else ''
            if not nxt.strip() or has_tib(nxt):
                err('check', f'{i+1}: orphaned Tibetan line: {l[:50]}')
        if not has_tib(l) and re.search(f'[{TIB}]', l):
            err('check', f'{i+1}: Tibetan character in a target-language line')

    # warning: phonetics vs. syllables
    for i in range(len(lines) - 1):
        if has_tib(lines[i]) and looks_like_pho(lines[i + 1]):
            a, b = syl(lines[i]), len(pho_tokens(lines[i + 1]))
            if b and abs(a - b) > 2:
                warn('check', f'{i+2}: phonetics has {b} words, Tibetan {a} syllables '
                              f'— possibly shifted: {lines[i+1][:40]}')

    # warning: recitability — relative expansion above the published-translations p99 (~1% of lines)
    max_ratio = getattr(args, 'max_ratio', OUTLIER_EXPANSION)
    for ln, tib, pho, cz in verse_triplets(lines):
        t, c = syl(tib), target_syl(cz)
        if t >= 4 and c and c / t > max_ratio:
            warn('check', f'{ln+2}: {c} target-language syllables for {t} Tibetan '
                          f'({c/t:.2f}× against median {MEDIAN_EXPANSION:.2f}×) '
                          f'— probably an explanatory gloss in the verse: {cz.strip()[:60]}')
    # warning: drift against the glossary — the only safeguard against the triplet bank
    # and --reuse pulling in a term the glossary has already rejected (see the
    # Terminology section in SKILL.md)
    gpath = args.glossary or default_glossary()
    print(f'note: glossary = {gpath}', file=sys.stderr)
    for r, _, bad in glossary_drift([g for g in load_glossary(gpath)
                                     if g['status'] == 'fixed'], lines):
        for ln, cz in bad[:3]:
            warn('check', f'{ln}: glossary requires "{r["target"]}" for '
                          f'{r["wylie"] or r["tib"]}: {cz[:60]}')

    print(f'{args.text}: checked {len(lines)} lines')
    return finish('check')


# --------------------------------------------------- 9. consist + selftest

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
    """The same Tibetan line → the same target-language rendering across finished texts of a cycle.

    `glossary --check` is per-text and per-term; this guards whole lines. That is
    exactly what the triplet bank is supposed to ensure, but the bank only applies at
    build time — a text assembled before its sibling existed never learns of it.
    """
    seen = {}          # key_tib -> {target text: [texts]}
    for _, text, p in iter_texts(args.corpus, '**/text.md'):
        lines = p.read_text(encoding='utf-8').split('\n')
        for i in range(front_matter_end(lines), len(lines)):
            if not has_tib(lines[i]):
                continue
            czs = target_lines(lines, i)
            if not czs:
                continue
            cz = ' / '.join(c.strip() for c in czs)
            key = key_tib(lines[i])
            if len(key) < 8:                 # short lines (mantras, markers) aren't judged
                continue
            seen.setdefault(key, {}).setdefault(cz, []).append(text[:38])

    clashes = {k: v for k, v in seen.items() if len(v) > 1}
    shared = sum(1 for v in seen.values() if sum(len(t) for t in v.values()) > 1)
    print(f'# consist: {len(seen)} unique Tibetan lines, '
          f'{shared} repeat across texts')
    for key, variants in sorted(clashes.items(), key=lambda x: -len(x[1]))[:args.max]:
        warn('consist', f'{len(variants)} different translations of the same line:')
        for cz, texts in variants.items():
            print(f'    [{", ".join(sorted(set(texts)))}] {cz[:110]}')
    if not clashes:
        print('  ok  no Tibetan line has two different renderings across texts')
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
            assert recon == norm_tib(text), f'{name}: reconstruction'
            assert all(not is_punct_only(s.tib) for s in segs.values()), f'{name}: punct-only'
            types = [s.type for s in sorted(segs.values(), key=lambda s: float(s.num))]
            print(f'selftest {name}: {len(segs)} segments, types {types}')
            if name == 'terma':
                assert 'mantra' in types, 'mantra not detected'
                assert types[0] == 'heading', 'heading not detected'
            else:
                assert len(segs) >= 3, 'shad mode: ༈ did not split units'

    assert target_syl('mou drahou zemi') == 5, 'target_syl: vowel-run count'
    assert target_syl('KÉŽ SE JEJICH KLAM') == 5, 'target_syl: uppercase + accented'
    assert pho_tokens('Kéž se jejich klam, rozplyne!') == \
        ['kéž', 'se', 'jejich', 'klam', 'rozplyne'], 'pho_tokens: diacritics'
    assert pho_tokens("SEM PA’I ŽÄL") == ['sem', 'pa', 'i', 'žäl'], 'pho_tokens: apostrophe'
    print('selftest target_syl + pho_tokens: OK')

    _warn = _err = 0
    lint_pho(1, 'verse', 'LÁMA', pho_lint=True)
    assert _warn == 1, 'lint_pho: length mark must warn with --pho-lint'
    _warn = _err = 0
    lint_pho(1, 'verse', 'LÁMA', pho_lint=False)
    assert _warn == 0, 'lint_pho: length mark must not warn without --pho-lint'
    _warn = _err = 0
    print('selftest lint_pho: OK')

    tib = 'ངོ་བོ་ཉིད།'
    assert target_lines([tib, 'NGO WO ŇI', 'esence sama'], 0) == ['esence sama'], \
        'target_lines: verse'
    assert target_lines([tib, 'ngo wo ňi', 'esence sama'], 0) == ['esence sama'], \
        'target_lines: verse with old lowercase phonetics'
    assert target_lines([tib, 'OM AH HUNG'], 0) == [], 'target_lines: mantra'
    assert target_lines([tib, 'recitujte sedmkrát'], 0) == ['recitujte sedmkrát'], \
        'target_lines: rubric without punctuation'

    grow = [dict(tib='ངོ་བོ', wylie='ngo bo', target='esence', stem='esenc',
                 status='fixed', note='')]
    assert not glossary_drift(grow, [tib, 'NGO WO ŇI', 'esence sama'])[0][2], \
        'glossary_drift: false alarm'
    assert glossary_drift(grow, [tib, 'NGO WO ŇI', 'podstata sama'])[0][2], \
        'glossary_drift: drift not caught'
    print('selftest target_lines + glossary_drift: OK')

    doc = [tib, 'NGO WO ŇI', 'esence sama', '',
           tib, 'OM AH HUNG', '',
           tib, 'kéž se jejich klam rozplyne', '',
           'recitujte třikrát']
    got = [(n, c) for n, c in target_line_numbers(doc) if c]
    assert got == [(3, 'esence sama'), (9, 'kéž se jejich klam rozplyne'),
                   (11, 'recitujte třikrát')], f'target_line_numbers: {got}'
    assert all(doc[n - 1] == c for n, c in got), 'target_line_numbers: line numbers'
    assert not any(has_tib(c) or looks_like_iast(c) for _, c in got), \
        'target_line_numbers: Tibetan in the export'
    print('selftest target_line_numbers: OK')

    # --- load_bank: its own folder is excluded, otherwise a build reads its own output
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        for name, cz in (('a', 'z textu A'), ('b', 'z textu B')):
            d = root / name
            d.mkdir()
            (d / 'text.md').write_text(f'{tib}\nNGO WO ŇI\n{cz}\n', encoding='utf-8')
        assert len(load_bank(root)) >= 1, 'load_bank: loaded nothing'
        both = load_bank(root)[key_tib(tib)][1]
        only_b = load_bank(root, exclude_dir=root / 'a')[key_tib(tib)][1]
        assert only_b == 'z textu B', f'load_bank: exclude_dir does not work ({only_b})'
        assert both in ('z textu A', 'z textu B'), 'load_bank: unexpected content'
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
                   help='LABEL=path[,path2] (multiple paths = a split run)')
    p.add_argument('-o', '--out')
    p.add_argument('--ratio', type=float, default=0.4)
    p.set_defaults(fn=cmd_compare)

    p = sub.add_parser('build')
    p.add_argument('--source', required=True)
    p.add_argument('--base', action='append', required=True)
    p.add_argument('--reuse')
    p.add_argument('--pho')
    p.add_argument('--mantra')
    p.add_argument('--overrides')
    p.add_argument('--front')
    p.add_argument('--back')
    p.add_argument('-o', '--out')
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--allow-gaps', action='store_true')
    p.add_argument('--pho-lint', action='store_true',
                   help='enable target-language transcription lints from the phonetics file '
                        '(vowel-length marks, PHET, TSH/CCH)')
    p.set_defaults(fn=cmd_build)

    p = sub.add_parser('glossary', help='global glossary as data')
    p.add_argument('--corpus', help='folder of texts to check for drift (--check)')
    p.add_argument('--file', help='glossary.tsv; empty stem = exact target string; '
                        'inflecting languages should fill stem; '
                        'defaults to ./glossary.tsv or the skill default')
    p.add_argument('--max', type=int, default=12)
    g = p.add_mutually_exclusive_group()
    g.add_argument('--prompt', action='store_true')
    g.add_argument('--check', action='store_true')
    p.set_defaults(fn=cmd_glossary)

    p = sub.add_parser('consist', help='the same Tibetan line → the same target-language text across texts')
    p.add_argument('--corpus', required=True)
    p.add_argument('--max', type=int, default=20)
    p.set_defaults(fn=cmd_consist)

    p = sub.add_parser('meter', help='recitability: relative expansion target-language/Tibetan')
    p.add_argument('text')
    p.add_argument('--max-ratio', type=float, default=OUTLIER_EXPANSION)
    p.add_argument('--max', type=int, default=10)
    p.set_defaults(fn=cmd_meter)

    p = sub.add_parser('target', aliases=['czech'], help='only the target-language lines, numbered — for a proofreader')
    p.add_argument('text')
    p.set_defaults(fn=cmd_target)

    p = sub.add_parser('check')
    p.add_argument('text')
    p.add_argument('--source')
    p.add_argument('--original')
    p.add_argument('--glossary', help='glossary.tsv; empty stem = exact target string; '
                                       'inflecting languages should fill stem; '
                                       'defaults to ./glossary.tsv or the skill default')
    p.add_argument('--max-ratio', type=float, default=OUTLIER_EXPANSION)
    p.set_defaults(fn=cmd_check)

    p = sub.add_parser('selftest')
    p.set_defaults(fn=cmd_selftest)

    args = ap.parse_args()
    if args.cmd == 'build' and not args.out and not args.dry_run:
        ap.error('build: -o/--out is required (or --dry-run)')
    sys.exit(args.fn(args) or 0)


if __name__ == '__main__':
    main()
