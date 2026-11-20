#!/usr/bin/env python3
"""Render _pages/publications.md from the CV's publications.bib.

publications.bib is the single source of truth (see personal/cv/CLAUDE.md).
_pages/publications.md is GENERATED — do not hand-edit it. To change a
publication, edit the bib entry and rerun this script.

Usage:
    uv run --with 'bibtexparser<2' --with pyyaml tools/render_publications.py [BIB_PATH]

bibtexparser must stay below 2: this script uses the v1 API (`bibtexparser.load`),
which v2 removed, so an unpinned `--with bibtexparser` crashes.

BIB_PATH defaults to ~/claude/personal/cv/publications.bib. Extras that
don't live in the bib (video/dataset links, local PDF fallbacks for old
papers with no DOI) come from _data/pub_extras.yml, keyed by bib entry key.

ORDER: newest first. An entry's sort date is its printed year, then its bib
`month` (full names or abbreviations), then the day if `by_key.<key>.date` in
pub_extras.yml gives one. That sidecar `date` (YYYY, YYYY-MM or YYYY-MM-DD)
is for entries whose bib has no month, or a month that is not when the paper
became public; its year must equal the printed year, or the script stops, so
the list can never look out of order. Equal dates keep bib order.

SELECTED: the home page also shows the entries keyworded `selected` in the bib (the same flag that puts
a paper on the 1-page CV, so there is one place to choose them). They are written to
_data/selected_pubs.yml, in page order, from the same render_entry text as the publications page.

CONFIDENTIALITY: this page is public. Any entry keyworded `inreview`, or
whose `note` field mentions "under review", is dropped before rendering --
see is_confidential() below. The selected list passes through the same filter (public_entries()), so
a paper cannot reach the home page by being flagged `selected` while under review. That is a deliberate, load-bearing filter, not
an incidental one: personal/cv/publications.bib may legitimately carry
confidential manuscripts for the private cv_academic/cv_grant variants, and
this script must never surface them here. Do not remove or weaken the
filter without re-checking every current `inreview`/preprint entry by hand.
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
SELECTED_PATH = SITE_ROOT / "_data" / "selected_pubs.yml"
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
     Regenerate: uv run --with 'bibtexparser<2' --with pyyaml tools/render_publications.py
     Confidential work under review (keyword `inreview`, or any entry whose
     note mentions "under review") is excluded from this public page by design. -->

"""

UNDER_REVIEW_RE = re.compile(r"under review", re.IGNORECASE)

MONTH_NUMBERS = {name: i for i, name in enumerate(MONTHS, start=1)}  # keyed by 3-letter prefix


def month_number(raw) -> int:
    """1-12 for a bib month ("feb", "Oct", "September"); 0 when blank or not a month."""
    prefix = (raw or "").strip().lower()[:3]
    return MONTH_NUMBERS.get(prefix, 0)


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


def is_confidential(entry: dict) -> bool:
    """True if this entry must never reach the public site.

    Two independent checks, either one is sufficient: the bib's own
    `inreview` keyword, and a substring match on the note field. The note
    check is a backstop in case an entry is ever mis-keyworded -- an
    `inreview` entry's note should always say "under review" anyway.
    """
    keywords = entry.get("keywords", "")
    if any(k.strip().lower() == "inreview" for k in keywords.split(",")):
        return True
    if UNDER_REVIEW_RE.search(entry.get("note", "")):
        return True
    return False


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

    return f"1. {authors} {year}. {title_md}. {venue}{note_str}{extra_str}"


def printed_year(entry: dict) -> int:
    """The year render_entry prints, as an int (0 when the entry has none, which sorts last)."""
    text = entry.get("year") or entry.get("date", "")[:4]
    return int(text) if text.isdigit() else 0


def sort_date(entry: dict, extras: dict) -> tuple[int, int, int]:
    """(year, month, day) used to order the page; see the ORDER note in the module docstring."""
    year = printed_year(entry)
    month = month_number(entry.get("month"))
    day = 0
    override = str(extras.get("by_key", {}).get(entry.get("ID", ""), {}).get("date", "")).strip()
    if override:
        parts = [int(p) for p in override.split("-")]
        if parts[0] != year:
            raise ValueError(
                f"{entry.get('ID')}: pub_extras date {override} is not in the printed year {year}; "
                "fix the bib year or the date so the list stays in order")
        month = parts[1] if len(parts) > 1 else 0
        day = parts[2] if len(parts) > 2 else 0
    return (year, month, day)


def public_entries(entries: list[dict]) -> tuple[list[dict], int]:
    """The entries that may appear on a public page, and how many confidential ones were dropped.

    Every public output of this script (the publications page and the selected list) takes its entries from here.
    """
    public = [e for e in entries if not is_confidential(e)]
    return public, len(entries) - len(public)


def build_body(entries: list[dict], extras: dict) -> tuple[str, int]:
    """Markdown list of the public entries, newest first, and how many confidential ones were dropped."""
    public, skipped_confidential = public_entries(entries)
    rendered = [(sort_date(entry, extras), render_entry(entry, extras)) for entry in public]

    for extra in extras.get("extra_entries", []):
        rendered.append(((int(extra["year"]), 0, 0), extra["line"].strip()))

    # Newest first. reverse=True keeps the original order of equal keys, so ties follow the bib.
    rendered.sort(key=lambda r: r[0], reverse=True)
    return "\n".join(line for _, line in rendered) + "\n", skipped_confidential


def is_selected(entry: dict) -> bool:
    return any(k.strip().lower() == "selected" for k in entry.get("keywords", "").split(","))


def build_selected(entries: list[dict], extras: dict) -> tuple[list[dict], int]:
    """The `selected` public entries, newest first, as {key, year, citation}; and how many selected ones were
    dropped as confidential. `citation` is the publications-page line without its list marker."""
    flagged = [e for e in entries if is_selected(e)]
    public, dropped = public_entries(flagged)
    public.sort(key=lambda e: sort_date(e, extras), reverse=True)  # stable: ties keep bib order
    items = [{"key": e.get("ID", ""), "year": printed_year(e),
              "citation": render_entry(e, extras).removeprefix("1. ")} for e in public]
    return items, dropped


SELECTED_HEADER = """# GENERATED by tools/render_publications.py. Do not hand-edit.
# The bib entries keyworded `selected` (the 1-page CV's list), minus anything confidential, newest first.
# Shown on the home page; change the selection by toggling `selected` in personal/cv/publications.bib.
"""


def render_selected_yaml(items: list[dict]) -> str:
    return SELECTED_HEADER + yaml.safe_dump(items, sort_keys=False, allow_unicode=True, width=1000)


def render_all(bib_path: Path) -> tuple[str, str, int, int]:
    """(publications page text, selected_pubs.yml text, confidential entries dropped from the page,
    confidential entries dropped from the selected list). Pure: writes nothing."""
    with open(bib_path) as f:
        db = bibtexparser.load(f)
    extras = load_extras()
    body, skipped_confidential = build_body(db.entries, extras)
    selected, dropped_selected = build_selected(db.entries, extras)
    return HEADER + body, render_selected_yaml(selected), skipped_confidential, dropped_selected


def main():
    bib_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_BIB
    if not bib_path.exists():
        sys.exit(f"bib not found: {bib_path}")

    page, selected_yaml, skipped_confidential, dropped = render_all(bib_path)
    OUTPUT_PATH.write_text(page)
    SELECTED_PATH.write_text(selected_yaml)
    print(f"Wrote {page.count(chr(10)) - HEADER.count(chr(10))} entries to {OUTPUT_PATH}"
          f" ({skipped_confidential} confidential entries excluded)")
    print(f"Wrote {selected_yaml.count('- key:')} selected entries to {SELECTED_PATH}")
    if dropped:
        print(f"WARNING: {dropped} entries keyworded `selected` are confidential and were left out;"
              " remove `selected` from them in the bib.", file=sys.stderr)


if __name__ == "__main__":
    main()
