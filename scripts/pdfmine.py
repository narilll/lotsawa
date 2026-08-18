#!/usr/bin/env python3
"""Těžba hotových interlineárních PDF překladů (tibetština / fonetika / čeština).

Usage:
  pdfmine.py triage   <dir|pdf>...                      # lze těžit? verdikt na PDF
  pdfmine.py extract  <dir|pdf>... -o <mined dir>       # blocks.tsv + normalizovaný .txt
  pdfmine.py lexicon  <mined dir> [-o pho_lexicon.tsv]  # slabika → přepis + konflikty
  pdfmine.py bank     <mined dir> [-o triplet_bank.tsv] # celé trojice pro build --reuse-bank
  pdfmine.py arbitrate <mined dir> --glossary <tsv>     # co PDF říkají k závazným termínům
  pdfmine.py style    <mined dir>                       # expanze a tvar rubrik vs. náš korpus

Vstup se nemodifikuje, PDF jsou read-only zdroj. Každý vytěžený řádek nese
provenienci (soubor + strana), jinak nelze později rozhodnout spor.
Vyžaduje `pdftotext` (poppler). Jinak stdlib; predikáty se přebírají z lotsawa.py.
"""
import argparse
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lotsawa import (TIB, has_tib, key_tib, syl, cz_syl, fold, norm_tib,  # noqa: E402
                     looks_like_iast, MEDIAN_EXPANSION)

PAGE_BREAK = '\x0c'
IMPERATIVE = re.compile(r'\b(recituj|vizualizuj|připrav|prones|obětuj|medituj|zopakuj|'
                        r'nech|představ|drž|polož|vlož|zapečeť|rozpusť|recitujte|'
                        r'vizualizujte|prones|obětujte)', re.I)


def pdftotext(path):
    r = subprocess.run(['pdftotext', '-layout', str(path), '-'],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(f'ERROR pdftotext: {path.name}: {r.stderr.strip()[:120]}', file=sys.stderr)
        return ''
    return r.stdout


def pdf_pages(path):
    return pdftotext(path).split(PAGE_BREAK)


def strip_furniture(pages):
    """Odstraní hlavičky/patičky (řádky na ≥ 50 % stran) a čísla stran."""
    seen = Counter()
    for p in pages:
        for l in {x.strip() for x in p.split('\n') if x.strip()}:
            seen[l] += 1
    thresh = max(2, len(pages) // 2)
    furniture = {l for l, n in seen.items() if n >= thresh and not has_tib(l)}
    out = []
    for p in pages:
        keep = []
        for l in p.split('\n'):
            s = l.strip()
            if not s or s in furniture or re.fullmatch(r'[\d\s|/–-]{1,12}', s):
                keep.append('')
            else:
                keep.append(l)
        out.append('\n'.join(keep))
    return out, sorted(furniture)[:10]


def page_blocks(page):
    """Bloky = skupiny po sobě jdoucích neprázdných řádků."""
    blocks, cur = [], []
    for l in page.split('\n'):
        if l.strip():
            cur.append(l.strip())
        elif cur:
            blocks.append(cur)
            cur = []
    if cur:
        blocks.append(cur)
    return blocks


CZ_ONLY_CHARS = 'ÁÍÝĚŘŮÓáíýěřůó'   # v přepisu se nevyskytují (jen Ä Ö Ü)


def looks_uppercase_pho(line):
    """Fonetika v PDF bývá VERZÁLKAMI, ale tak i české titulky — je nutné je odlišit.

    Rozlišuje: (a) české znaky, které přepis nezná (Á Í Ý Ě Ř Ů Ó), (b) délku tokenů —
    slabika přepisu má 2–4 znaky (měřeno), české slovo je delší.
    """
    letters = [c for c in line if c.isalpha()]
    if not letters:
        return False
    if re.search(r'[.,;:!?]', line) or any(c in CZ_ONLY_CHARS for c in line):
        return False
    upper = sum(1 for c in letters if c.isupper()) / len(letters)
    if not (upper > 0.8 or not any(c.isupper() for c in letters)):
        return False
    toks = [t for t in line.split() if any(c.isalpha() for c in t)]
    if not toks:
        return False
    return sum(len(t) for t in toks) / len(toks) <= 4.6


def classify_block(block):
    """→ (typ, tib, pho, cz). Rozhoduje POZICE v bloku, ne styl řádku."""
    tibs = [l for l in block if has_tib(l)]
    if not tibs:
        return ('cz_only', '', '', ' '.join(block)) if block else None
    tib = ' '.join(tibs)
    rest = [l for l in block if not has_tib(l)]
    if not rest:
        return 'heading', tib, '', ''
    if len(rest) == 1:
        # tib + jeden řádek: rubrika (překlad) nebo verš bez překladu (fonetika)
        if looks_uppercase_pho(rest[0]) and abs(len(rest[0].split()) - syl(tib)) <= 2:
            return 'verse_nocz', tib, rest[0], ''
        return 'rubric', tib, '', rest[0]
    pho, cz = rest[0], ' '.join(rest[1:])
    # Fonetika musí mít přibližně tolik tokenů, kolik má tibetština slabik. Bez téhle
    # kontroly se za fonetiku vydává český titul psaný verzálkami a zanáší lexikon.
    if not (looks_uppercase_pho(pho) and abs(len(pho.split()) - syl(tib)) <= 2):
        return 'rubric', tib, '', ' '.join(rest)
    if looks_like_iast(pho) or looks_like_iast(cz):
        return 'mantra', tib, pho, cz
    return 'verse', tib, pho, cz


def iter_pdfs(paths):
    for p in paths:
        p = Path(p)
        if p.is_dir():
            yield from sorted(x for x in p.rglob('*.pdf') if 'mined' not in x.parts)
        elif p.suffix.lower() == '.pdf':
            yield p


def verdict(text, triples):
    tib = len(re.findall(f'[{TIB}]', text))
    chars = len(text.strip())
    if chars < 200:
        return 'scan', tib, chars
    if tib < chars * 0.02:
        return 'legacy', tib, chars
    return ('text' if triples else 'text?'), tib, chars


# ------------------------------------------------------------------- triage

def cmd_triage(args):
    rows = []
    for pdf in iter_pdfs(args.paths):
        pages = pdf_pages(pdf)
        text = '\n'.join(pages)
        clean, _ = strip_furniture(pages)
        triples = sum(1 for pg in clean for b in page_blocks(pg)
                      if (classify_block(b) or ('',))[0] in ('verse', 'mantra'))
        v, tib, chars = verdict(text, triples)
        rows.append((v, pdf.name, len(pages), chars, tib, triples))
    if not rows:
        print('žádná PDF nenalezena', file=sys.stderr)
        return 2
    print(f'{"verdikt":8} {"stran":>5} {"znaků":>7} {"tib":>6} {"trojic":>6}  soubor')
    for v, name, pg, chars, tib, tr in sorted(rows):
        print(f'{v:8} {pg:>5} {chars:>7} {tib:>6} {tr:>6}  {name[:58]}')
    tally = Counter(r[0] for r in rows)
    print('\n' + ', '.join(f'{k} {v}' for k, v in sorted(tally.items())), file=sys.stderr)
    if tally.get('text', 0) + tally.get('text?', 0) == 0:
        print('ERROR: žádné PDF není automaticky těžitelné', file=sys.stderr)
        return 1
    return 0


# ------------------------------------------------------------------ extract

def cmd_extract(args):
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    tsv = [['pdf', 'strana', 'typ', 'tib', 'pho', 'cz']]
    stats = Counter()
    for pdf in iter_pdfs(args.paths):
        pages = pdf_pages(pdf)
        clean, furniture = strip_furniture(pages)
        (out / (pdf.stem + '.txt')).write_text('\n\n'.join(clean), encoding='utf-8')
        n = 0
        for pno, page in enumerate(clean, 1):
            for b in page_blocks(page):
                c = classify_block(b)
                if not c:
                    continue
                typ, tib, pho, cz = c
                if typ == 'cz_only':
                    continue
                tsv.append([pdf.name, str(pno), typ, tib, pho, cz])
                stats[typ] += 1
                n += 1
        print(f'{pdf.name[:52]:52} {len(pages):>3} stran, {n:>4} bloků'
              + (f', furniture: {len(furniture)}' if furniture else ''))
    (out / 'blocks.tsv').write_text(
        '\n'.join('\t'.join(r) for r in tsv) + '\n', encoding='utf-8')
    print(f'\n{out}/blocks.tsv: {len(tsv)-1} bloků — '
          + ', '.join(f'{k} {v}' for k, v in stats.most_common()), file=sys.stderr)
    return 0


def load_blocks(mined):
    p = Path(mined) / 'blocks.tsv'
    rows = []
    for i, line in enumerate(p.read_text(encoding='utf-8').splitlines()):
        if i == 0:
            continue
        f = line.split('\t')
        f += [''] * (6 - len(f))
        rows.append(dict(zip(('pdf', 'page', 'type', 'tib', 'pho', 'cz'), f[:6])))
    return rows


# ------------------------------------------------------------------ lexicon

def tib_syllables(line):
    """Slabiky; `ཿ` dělí i bez tsheg — jinak se ཨཱཿཧཱུྃ počítá jako jedna a zarovnání
    fonetiky se tiše posune (mantra Vadžraguru otrávila lexikon právě takto)."""
    core = re.sub(f'[^{TIB}]', ' ', line)
    core = re.sub(r'[།༎༈༔༄༅༃]', ' ', core)
    core = re.sub(r'ཿ(?=[^་\s])', 'ཿ་', core)
    return [s for s in re.split(r'[་\s]+', core) if s]


COL_SEP = '·'


def split_columns(tib, pho, cz=''):
    """Dvoukolonová sazba vzorů: `·` odděluje dva verše na jednom řádku.

    Bez tohoto dělení se zarovnávaly celé dvojverší a chyby se **vyrušily**:
    v `HUNG ORGJEN JÜL GJI NUB ČHANG TSHAM · PEMA GE SAR DONG PO LA` pokrývá
    ORGJEN dvě slabiky (ཨོ་རྒྱན) a `·` nulu, takže počet slabik i tokenů byl 14
    a mapování posunuté o jednu — tak se do lexikonu dostalo ནུབ→ČHANG,
    བྱང→TSHAM, མཚམས→`·`. Kolona se proto zarovnává samostatně; kolona se slitým
    tokenem prostě neprojde kontrolou počtů a zahodí se, místo aby otrávila zbytek.

    Vrací seznam trojic (tib, pho, cz). Nespárovatelný počet kolon → jeden celek.
    """
    if COL_SEP not in pho and COL_SEP not in cz:
        return [(tib, pho, cz)]
    parts = {
        'tib': [p.strip() for p in re.split(r'(?<=[༔།])\s+', tib) if p.strip()],
        'pho': [p.strip() for p in pho.split(COL_SEP) if p.strip()],
        'cz': [p.strip() for p in cz.split(COL_SEP) if p.strip()] if cz.strip() else None,
    }
    n = len(parts['pho']) if pho.strip() else len(parts['cz'] or [])
    for v in parts.values():
        if v is not None and len(v) != n:
            return [(tib, pho, cz)]
    if n < 2:
        return [(tib, pho, cz)]
    return [(parts['tib'][i],
             parts['pho'][i] if pho.strip() else '',
             parts['cz'][i] if parts['cz'] else '') for i in range(n)]


def cmd_lexicon(args):
    pairs = defaultdict(Counter)
    src = {}
    aligned = skipped = 0
    for r in load_blocks(args.mined):
        if r['type'] not in ('verse', 'verse_nocz') or not r['pho']:
            continue
        for tib_c, pho_c, _ in split_columns(r['tib'], r['pho'], r['cz']):
            sylls = tib_syllables(tib_c)
            toks = pho_c.split()
            if len(sylls) != len(toks) or not sylls:
                skipped += 1
                continue
            aligned += 1
            for s, t in zip(sylls, toks):
                pairs[s][t.strip('.,;:!?')] += 1
                src.setdefault((s, t), f"{r['pdf']}:{r['page']}")
    out = Path(args.out) if args.out else Path(args.mined) / 'pho_lexicon.tsv'
    lines = ['# slabika\tpřepis\tpočet\tvarianty\tzdroj']
    for s, c in sorted(pairs.items(), key=lambda x: -sum(x[1].values())):
        best, n = c.most_common(1)[0]
        variants = ' | '.join(f'{k} {v}×' for k, v in c.most_common()[1:4])
        lines.append(f'{s}\t{best}\t{n}\t{variants}\t{src.get((s, best), "")}')
    out.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f'{out}: {len(pairs)} slabik z {aligned} zarovnaných řádků '
          f'({skipped} nezarovnatelných)')

    # konfliktní report proti phonetics.md
    print('\n=== úzus PDF vs. pravidla phonetics.md')
    probes = [
        ('ཧཱུྃ', 'húng / hung'), ('ཕཊ', 'phe (ne phat)'), ('གསོལ', 'sol (koncové -l bez přehlásky)'),
        ('ཐུགས', 'thuk'), ('མཆོག', 'čhok'), ('ཚོགས', 'cchok'), ('རྩལ', 'cal'),
        ('འཁྲུལ', 'thrul'), ('ཡེ', 'je'), ('ཤེས', 'še'), ('རྡོ', 'dor'), ('རྗེ', 'dže'),
    ]
    for s, rule in probes:
        if s in pairs:
            got = ' | '.join(f'{k} {v}×' for k, v in pairs[s].most_common(3))
            print(f'  {s:8} pravidlo: {rule:34} PDF: {got}')
    upper = sum(1 for c in pairs.values() for t in c
                if any(ch.isupper() for ch in t))
    print(f'\n  velká písmena ve fonetice: {upper} z {sum(len(c) for c in pairs.values())} tvarů')
    return 0


# --------------------------------------------------------------------- bank

def cmd_bank(args):
    bank, src = {}, {}
    coll = Counter()
    for r in load_blocks(args.mined):
        if r['type'] not in ('verse', 'mantra', 'rubric') or not r['cz'].strip():
            continue
        # Bez dělení kolon nesl klíč celé dvojverší a nikdy se netrefil na náš
        # jednoveršový segment — proto banka nepokrývala ani Sedmiřádkovou modlitbu.
        for tib_c, pho_c, cz_c in split_columns(r['tib'], r['pho'], r['cz']):
            if not cz_c.strip():
                continue
            k = key_tib(tib_c)
            if not k:
                continue
            if k in bank and bank[k][1] != cz_c:
                coll[k] += 1
            bank[k] = (pho_c, cz_c)
            src[k] = f"{r['pdf']}:{r['page']}"
    out = Path(args.out) if args.out else Path(args.mined) / 'triplet_bank.tsv'
    lines = ['# key_tib\tpho\tcz\tzdroj']
    for k, (pho, cz) in bank.items():
        lines.append(f'{k}\t{pho}\t{cz}\t{src[k]}')
    out.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f'{out}: {len(bank)} trojic'
          + (f', {len(coll)} kolizí (týž tibetský řádek, jiná čeština)' if coll else ''))
    return 0


# ---------------------------------------------------------------- arbitrate

def cmd_arbitrate(args):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from lotsawa import load_glossary
    rows = load_glossary(args.glossary)
    blocks = load_blocks(args.mined)
    print(f'# arbitráž {len(rows)} termínů proti {len(blocks)} blokům z PDF\n')
    for r in rows:
        tkey = key_tib(r['tib'])
        if not tkey:
            continue
        hits = [b for b in blocks if tkey in key_tib(b['tib']) and b['cz'].strip()]
        if not hits:
            continue
        ours = fold(r['stem'])
        agree = [h for h in hits if ours in fold(h['cz'])]
        label = (r['wylie'] or r['tib']) + ' → ' + (r['czech'] or '(nerozhodnuto)')
        print(f'{label}  [{r["status"]}]  {len(agree)}/{len(hits)} shoda')
        for h in hits[:args.max]:
            mark = 'ok ' if ours in fold(h['cz']) else '!! '
            print(f'    {mark}{h["pdf"][:26]}:{h["page"]}  {h["cz"][:78]}')
    return 0


# -------------------------------------------------------------------- style

def cmd_style(args):
    ratios, rubrics, imper = [], 0, 0
    for r in load_blocks(args.mined):
        if r['type'] == 'verse' and r['cz'].strip():
            t, c = syl(r['tib']), cz_syl(r['cz'])
            if t >= 4 and c:
                ratios.append(c / t)
        elif r['type'] == 'rubric' and r['cz'].strip():
            rubrics += 1
            if IMPERATIVE.search(r['cz']):
                imper += 1
    if ratios:
        ratios.sort()
        n = len(ratios)
        print(f'expanze čeština/tibetština: {n} veršů | medián {ratios[n//2]:.2f}× | '
              f'p10 {ratios[int(n*.1)]:.2f}× | p90 {ratios[int(n*.9)]:.2f}× | '
              f'p99 {ratios[int(n*.99)]:.2f}×')
        print(f'náš korpus: medián {MEDIAN_EXPANSION:.2f}×')
    if rubrics:
        print(f'rubriky: {rubrics}, z toho rozpoznaný imperativ {imper} '
              f'({imper/rubrics:.0%})')
    return 0


# ----------------------------------------------------------------------- CLI

def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)

    p = sub.add_parser('triage')
    p.add_argument('paths', nargs='+')
    p.set_defaults(fn=cmd_triage)

    p = sub.add_parser('extract')
    p.add_argument('paths', nargs='+')
    p.add_argument('-o', '--out', required=True)
    p.set_defaults(fn=cmd_extract)

    p = sub.add_parser('lexicon')
    p.add_argument('mined')
    p.add_argument('-o', '--out')
    p.set_defaults(fn=cmd_lexicon)

    p = sub.add_parser('bank')
    p.add_argument('mined')
    p.add_argument('-o', '--out')
    p.set_defaults(fn=cmd_bank)

    p = sub.add_parser('arbitrate')
    p.add_argument('mined')
    p.add_argument('--glossary', required=True)
    p.add_argument('--max', type=int, default=6)
    p.set_defaults(fn=cmd_arbitrate)

    p = sub.add_parser('style')
    p.add_argument('mined')
    p.set_defaults(fn=cmd_style)

    args = ap.parse_args()
    sys.exit(args.fn(args) or 0)


if __name__ == '__main__':
    main()
