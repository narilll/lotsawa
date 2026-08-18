# Lotsawa

Claude Code skill pro překlad tibetských buddhistických textů (sádhany, modlitby, sur obětiny) do češtiny.

Překlad běží jako multi-agentní workflow: nezávislý překladatel, adversariální recenzent a kontrola zpětným překladem (čtyři plné drafty, pokud existuje anglický překlad), porovnání a finální montáž. Výstupem je `text.md` v interlineárním formátu definovaném ve skillu.

## Obsah

| Soubor | Účel |
|---|---|
| `SKILL.md` | Definice skillu — celý workflow, formátová a terminologická pravidla |
| `glossary.tsv` | Terminologický glosář (tibetština/angličtina → čeština) |
| `phonetics.md` | Pravidla české fonetické transkripce tibetštiny |
| `scripts/lotsawa.py` | Mechanické kroky: segmentace, porovnání draftů, fonetika, montáž, lint |
| `scripts/pdfmine.py` | Extrakce textu z PDF |
| `scripts/segment_lotsawa_epub.py` | Segmentace EPUB zdrojů |

## Instalace

Zkopíruj (nebo naklonuj) adresář do `.claude/skills/lotsawa` v projektu:

```
git clone https://github.com/narilll/lotsawa .claude/skills/lotsawa
```

Skill se aktivuje, když v Claude Code požádáš o překlad tibetského/anglického buddhistického textu do češtiny. Vstupem je soubor (EPUB, md, txt) nebo vložený text.
