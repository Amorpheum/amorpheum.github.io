#!/usr/bin/env python3
"""Render _pages/publications.md from the CV's publications.bib.

publications.bib is the single source of truth (see personal/cv/CLAUDE.md).
_pages/publications.md is GENERATED — do not hand-edit it. To change a
publication, edit the bib entry and rerun this script.

Usage:
    uv run --with bibtexparser tools/render_publications.py [BIB_PATH]

BIB_PATH defaults to ~/claude/personal/cv/publications.bib. Extras that
don't live in the bib (video/dataset links, local PDF fallbacks for old
papers with no DOI) come from _data/pub_extras.yml, keyed by bib entry key.
"""

import re
import sys
from pathlib import Path

import bibtexparser
import yaml

DEFAULT_BIB = Path.home() / "claude/personal/cv/publications.bib"
SITE_ROOT = Path(__file__).resolve().parent.parent
EXTRAS_PATH = SITE_ROOT / "_data" / "pub_extras.yml"
OUTPUT_PATH = SITE_ROOT / "_pages" / "publications.md"
OWNER_FAMILY = "choo"  # bolds any author with this family name

MONTHS = {
    "jan": "Jan.", "feb": "Feb.", "mar": "Mar.", "apr": "Apr.",
    "may": "May", "jun": "Jun.", "jul": "Jul.", "aug": "Aug.",
    "sep": "Sep.", "oct": "Oct.", "nov": "Nov.", "dec": "Dec.",
}

HEADER = """---
layout: archive
title: "Publications"
permalink: /publications/
author_profile: true
---

<!-- GENERATED FILE. Do not hand-edit.
     Source: personal/cv/publications.bib (+ _data/pub_extras.yml)
     Regenerate: uv run --with bibtexparser tools/render_publications.py -->

"""


def strip_latex(s: str) -> str:
    if not s:
        return ""
    s = s.replace("{", "").replace("}", "")
    s = s.replace("\\&", "&").replace("\\%", "%").replace("\\_", "_")
    s = s.replace("--", "\u2013")
    s = re.sub(r"\\textbf\s*", "", s)
    s = re.sub(r"\\'e", "e\u0301", s)  # rare accent fallback
    s = re.sub(r"\s+", " ", s).strip()
    return s


def format_author(name: str) -> tuple[str, bool]:
    """'Last, First Middle' -> ('Last, F.M.', is_owner)."""
    name = strip_latex(name).strip()
    if "," in name:
        last, first = [p.strip() for p in name.split(",", 1)]
    else:
        parts = name.split()
        last, first = parts[-1], " ".join(parts[:-1])
    initials = "".join(f"{p[0]}." for p in first.split() if p)
    is_owner = last.lower() == OWNER_FAMILY
    formatted = f"{last}, {initials}" if initials else last
    if is_owner:
        formatted = f"**{formatted}**"
    return formatted, is_owner


def format_authors(author_field: str) -> str:
    names = [a.strip() for a in author_field.split(" and ") if a.strip()]
    formatted = [format_author(n)[0] for n in names]
    if len(formatted) == 1:
        return formatted[0]
    return ", ".join(formatted[:-1]) + " and " + formatted[-1]


def format_venue(entry: dict) -> str:
    venue = entry.get("booktitle") or entry.get("journal") or entry.get("howpublished") or ""
    venue = strip_latex(venue)

    context_bits = []
    if entry.get("address"):
        context_bits.append(strip_latex(entry["address"]))
    month = entry.get("month", "").strip().lower()
    year = entry.get("year") or (entry.get("date", "")[:4])
    if month in MONTHS:
        context_bits.append(f"{MONTHS[month]} {year}")
    elif year:
        context_bits.append(year)
    context = f" ({', '.join(context_bits)})" if context_bits else ""

    pages = entry.get("pages", "").replace("--", "\u2013")
    pages_str = f", {pages}" if pages else ""

    out = venue + context + pages_str
    return out.strip()


def format_note(entry: dict) -> str:
    raw = entry.get("note", "")
    if not raw:
        return "", False
    is_highlight = "\\textbf" in raw
    return strip_latex(raw), is_highlight


def load_extras() -> dict:
    if not EXTRAS_PATH.exists():
        return {}
    return yaml.safe_load(EXTRAS_PATH.read_text()) or {}


def render_entry(entry: dict, extras: dict) -> str:
    key = entry.get("ID", "")
    authors = format_authors(entry.get("author", ""))
    year = entry.get("year") or (entry.get("date", "")[:4]) or "n.d."
    title = strip_latex(entry.get("title", "Untitled"))

    link = entry.get("doi")
    link_url = f"https://doi.org/{link}" if link else entry.get("url")
    title_md = f"[{title}]({link_url})" if link_url else title

    venue = format_venue(entry)
    note, note_highlight = format_note(entry)

    extra = extras.get("by_key", {}).get(key, {})
    extra_links = []
    if extra.get("video"):
        extra_links.append(f"([video]({extra['video']}))")
    if extra.get("dataset"):
        extra_links.append(f"([dataset]({extra['dataset']}))")
    if extra.get("pdf") and not link_url:
        title_md = f"[{title}]({extra['pdf']})"
    extra_str = (" " + " ".join(extra_links)) if extra_links else ""

    if note:
        note_str = f" **{note}**." if note_highlight else f" ({note})."
    else:
        note_str = "."

    line = f"1. {authors} {year}. {title_md}. {venue}{note_str}{extra_str}"
    return line, (year, entry.get("date", "") or year)


def main():
    bib_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_BIB
    if not bib_path.exists():
        sys.exit(f"bib not found: {bib_path}")

    with open(bib_path) as f:
        db = bibtexparser.load(f)

    extras = load_extras()

    rendered = []
    for entry in db.entries:
        line, sort_key = render_entry(entry, extras)
        rendered.append((sort_key, line))

    for extra in extras.get("extra_entries", []):
        year = str(extra["year"])
        rendered.append(((year, year), extra["line"].strip()))

    # newest first
    rendered.sort(key=lambda r: r[0], reverse=True)

    body = "\n".join(line for _, line in rendered) + "\n"
    OUTPUT_PATH.write_text(HEADER + body)
    print(f"Wrote {len(rendered)} entries to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
