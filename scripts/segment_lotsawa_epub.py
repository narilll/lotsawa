#!/usr/bin/env python3
"""Segment a Lotsawa House EPUB content file into lotsawa's drafts/source.md.

Usage: segment_lotsawa_epub.py <content.html> <output source.md>

Expects Lotsawa House paragraph classes: tib-verse / pho-verse / eng-verse,
tib-note / eng-note, tib / eng, pho-mantra / eng-mantra. A tib-verse followed by
pho-mantra is a mantra; the colophon starts at the rubric beginning ཅེས་པ་འདི་ཡང་.
Stdlib only.
"""
import html.parser
import sys


class ParaParser(html.parser.HTMLParser):
    TAGS = ('p', 'h1', 'h2', 'h3', 'h4', 'div')

    def __init__(self):
        super().__init__()
        self.out = []
        self.cur = None

    def handle_starttag(self, tag, attrs):
        if tag in self.TAGS:
            self.cur = {'tag': tag, 'cls': dict(attrs).get('class', ''), 'text': []}

    def handle_endtag(self, tag):
        if self.cur and tag == self.cur['tag']:
            t = ' '.join(''.join(self.cur['text']).split())
            if t:
                self.out.append((self.cur['cls'].split()[0] if self.cur['cls'] else '', t))
            self.cur = None

    def handle_data(self, d):
        if self.cur is not None:
            self.cur['text'].append(d)


def segment(paras):
    segs = []
    i, n = 0, len(paras)
    while i < n:
        cls, t = paras[i]
        nxt = paras[i + 1][0] if i + 1 < n else None
        nx2 = paras[i + 2][0] if i + 2 < n else None
        if cls == 'tib-verse' and nxt == 'pho-mantra':
            d = {'tib': t, 'pho': paras[i + 1][1]}
            if nx2 == 'eng-mantra':
                d['iast'] = paras[i + 2][1]
                i += 3
            else:
                i += 2
            segs.append(('mantra', d))
        elif cls == 'tib-verse':
            d = {'tib': t}
            if nxt == 'pho-verse':
                d['pho'] = paras[i + 1][1]
                i += 1
            if i + 1 < n and paras[i + 1][0] == 'eng-verse':
                d['en'] = paras[i + 1][1]
                i += 1
            segs.append(('verse', d))
            i += 1
        elif cls == 'tib-note':
            d = {'tib': t}
            if nxt == 'eng-note':
                d['en'] = paras[i + 1][1]
                i += 1
            segs.append(('rubric', d))
            i += 1
        elif cls == 'eng-note':
            segs.append(('rubric', {'en': t}))
            i += 1
        elif cls == 'tib':
            d = {'tib': t}
            if nxt == 'eng':
                d['en'] = paras[i + 1][1]
                i += 1
            segs.append(('heading', d))
            i += 1
        elif cls == 'eng':
            segs.append(('heading', {'en': t}))
            i += 1
        else:
            i += 1

    # everything from the "ces pa 'di yang" rubric onward is the colophon
    for idx in range(len(segs) - 1, -1, -1):
        typ, d = segs[idx]
        if typ == 'rubric' and d.get('tib', '').startswith('ཅེས་པ་འདི་ཡང་'):
            for j in range(idx, len(segs)):
                segs[j] = ('colophon', segs[j][1])
            break
    return segs


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__.strip())
    src, dst = sys.argv[1], sys.argv[2]
    p = ParaParser()
    p.feed(open(src, encoding='utf-8').read())
    segs = segment(p.out)
    title = next((d.get('en') or d['tib'] for t, d in segs if t == 'heading'), 'untitled')
    with open(dst, 'w', encoding='utf-8') as f:
        f.write(f"# Source: {title}\n")
        f.write("# pho: lines are the source's English-style phonetics — pronunciation crib only, translators ignore them.\n\n")
        for k, (typ, d) in enumerate(segs, 1):
            f.write(f"## {k} [{typ}]\n")
            for key in ('tib', 'pho', 'iast', 'en'):
                if d.get(key):
                    f.write(f"{key}: {d[key]}\n")
            f.write("\n")
    from collections import Counter
    counts = ', '.join(f"{v} {k}" for k, v in Counter(t for t, _ in segs).items())
    print(f"{len(segs)} segments ({counts}) -> {dst}")


if __name__ == '__main__':
    main()
