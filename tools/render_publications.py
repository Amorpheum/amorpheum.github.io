#!/usr/bin/env python3
"""Render _data/publications.yml (the Publications page's records) from the CV's publications.bib.

publications.bib is the single source of truth (see personal/cv/CLAUDE.md).
_data/publications.yml is GENERATED — do not hand-edit it. _pages/publications.html renders it. To change a
publication, edit the bib entry and rerun this script.

Usage:
    uv run --with 'bibtexparser<2' --with pyyaml tools/render_publications.py [BIB_PATH]

bibtexparser must stay below 2: this script uses the v1 API (`bibtexparser.load`),
which v2 removed, so an unpinned `--with bibtexparser` crashes.

BIB_PATH defaults to ~/claude/personal/cv/publications.bib. Extras that
don't live in the bib (video/dataset links, local PDF fallbacks for old
papers with no DOI, research areas) come from _data/pub_extras.yml, keyed by bib entry key.

RECORD: one per paper: key, year, type, title, authors (Markdown, the owner in bold), venue, note, award
(the bib note is bold, e.g. a CHI Honourable Mention), areas and links. `type` is the entry's type keyword
(one of _data/publication_types.yml); an entry with none, two, or an unknown one stops the script. `areas` are
slugs from _data/areas.yml, from pub_extras.yml `by_key.<key>.areas`; a paper with none is "other".

ORDER: newest first. An entry's sort date is its printed year, then its bib
`month` (full names or abbreviations), then the day if `by_key.<key>.date` in
pub_extras.yml gives one. That sidecar `date` (YYYY, YYYY-MM or YYYY-MM-DD)
is for entries whose bib has no month, or a month that is not when the paper
became public; its year must equal the printed year, or the script stops, so
the list can never look out of order. Equal dates keep bib order.

CONFIDENTIALITY: this page is public. Any entry keyworded `inreview` (submitted, under review) or `working`
(unpublished and not currently submitted, e.g. rejected and awaiting a new venue), or
whose `note` field mentions "under review", is dropped before rendering --
see is_confidential() below; every public output takes its entries from public_entries(). That is a
deliberate, load-bearing filter, not an incidental one: personal/cv/publications.bib may legitimately carry
confidential manuscripts for the private cv_master/cv_academic/cv_grant variants, and
this script must never surface them here. Do not remove or weaken the
filter without re-checking every current `inreview`/`working`/preprint entry by hand.
"""

import re
import sys
from pathlib import Path

import bibtexparser
import yaml

DEFAULT_BIB = Path.home() / "claude/personal/cv/publications.bib"
SITE_ROOT = Path(__file__).resolve().parent.parent
EXTRAS_PATH = SITE_ROOT / "_data" / "pub_extras.yml"
PUBLICATIONS_PATH = SITE_ROOT / "_data" / "publications.yml"
AREAS_PATH = SITE_ROOT / "_data" / "areas.yml"
TYPES_PATH = SITE_ROOT / "_data" / "publication_types.yml"
OWNER_FAMILY = "choo"  # bolds any author with this family name

MONTHS = {
    "jan": "Jan.", "feb": "Feb.", "mar": "Mar.", "apr": "Apr.",
    "may": "May", "jun": "Jun.", "jul": "Jul.", "aug": "Aug.",
    "sep": "Sep.", "oct": "Oct.", "nov": "Nov.", "dec": "Dec.",
}

UNDER_REVIEW_RE = re.compile(r"under review", re.IGNORECASE)

# bib keywords that mark a manuscript as confidential: never rendered on the public site
CONFIDENTIAL_KEYWORDS = {"inreview", "working"}

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
    `inreview` / `working` keywords (CONFIDENTIAL_KEYWORDS), and a substring
    match on the note field. The note check is a backstop in case an entry is
    ever mis-keyworded -- an `inreview` entry's note should usually say
    "under review" anyway. A `working` entry carries no such note, so its
    keyword is the only gate: never drop `working` from CONFIDENTIAL_KEYWORDS.
    """
    keywords = entry.get("keywords", "")
    if any(k.strip().lower() in CONFIDENTIAL_KEYWORDS for k in keywords.split(",")):
        return True
    if UNDER_REVIEW_RE.search(entry.get("note", "")):
        return True
    return False


def load_extras() -> dict:
    if not EXTRAS_PATH.exists():
        return {}
    return yaml.safe_load(EXTRAS_PATH.read_text()) or {}


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

    Every public output of this script takes its entries from here.
    """
    public = [e for e in entries if not is_confidential(e)]
    return public, len(entries) - len(public)


TYPE_NOT_GIVEN = "needs exactly one type keyword ({types}) in the bib `keywords`"


def entry_type(entry: dict, type_ids: set[str]) -> str:
    """The entry's one type keyword. `selected` (the 1-page CV's flag), `inreview` and `working` are flags, not types, and are ignored."""
    keywords = [k.strip().lower() for k in entry.get("keywords", "").split(",") if k.strip()]
    found = [k for k in keywords if k in type_ids]
    if len(found) != 1:
        raise ValueError(f"{entry.get('ID')}: {TYPE_NOT_GIVEN.format(types=', '.join(sorted(type_ids)))}; "
                         f"got keywords {keywords or 'none'}")
    return found[0]


def entry_areas(key: str, areas: list | None, area_slugs: set[str]) -> list[str]:
    """Research-area slugs from pub_extras.yml; an unknown slug stops the script, no area is "other"."""
    areas = areas or []
    unknown = [a for a in areas if a not in area_slugs]
    if unknown:
        raise ValueError(f"{key}: unknown research area {unknown}; known: {sorted(area_slugs)}")
    return list(areas) or ["other"]


def paper_links(entry: dict, extra: dict) -> list[dict]:
    link = entry.get("doi")
    url = f"https://doi.org/{link}" if link else entry.get("url")
    links = []
    if url or extra.get("pdf"):
        links.append({"label": "paper", "url": url or extra["pdf"]})
    for label in ("video", "dataset"):
        if extra.get(label):
            links.append({"label": label, "url": extra[label]})
    return links


def build_record(entry: dict, extras: dict, area_slugs: set[str], type_ids: set[str]) -> dict:
    key = entry.get("ID", "")
    extra = extras.get("by_key", {}).get(key, {})
    note, award = format_note(entry)
    return {
        "key": key,
        "year": printed_year(entry),
        "type": entry_type(entry, type_ids),
        "title": strip_latex(entry.get("title", "Untitled")),
        "authors": format_authors(entry.get("author", "")),
        "venue": format_venue(entry),
        "note": note,
        "award": award,
        "areas": entry_areas(key, extra.get("areas"), area_slugs),
        "links": paper_links(entry, extra),
    }


def build_extra_record(extra: dict, area_slugs: set[str], type_ids: set[str]) -> dict:
    """A hand-carried entry (pre-bib) from pub_extras.yml `extra_entries`, in the same shape as a bib record."""
    title = extra.get("title", "?")
    if extra.get("type") not in type_ids:
        raise ValueError(f"extra_entries '{title}': type must be one of {sorted(type_ids)}, got {extra.get('type')!r}")
    return {
        "key": extra.get("key", ""),
        "year": int(extra["year"]),
        "type": extra["type"],
        "title": title,
        "authors": extra["authors"],
        "venue": extra["venue"],
        "note": "",
        "award": False,
        "areas": entry_areas(title, extra.get("areas"), area_slugs),
        "links": extra.get("links", []),
    }


def build_records(entries: list[dict], extras: dict, area_slugs: set[str],
                  type_ids: set[str]) -> tuple[list[dict], int]:
    """The public papers as records, newest first, and how many confidential ones were dropped."""
    public, skipped_confidential = public_entries(entries)
    ranked = [(sort_date(e, extras), build_record(e, extras, area_slugs, type_ids)) for e in public]
    for extra in extras.get("extra_entries", []):
        ranked.append(((int(extra["year"]), 0, 0), build_extra_record(extra, area_slugs, type_ids)))

    # Newest first. reverse=True keeps the original order of equal keys, so ties follow the bib.
    ranked.sort(key=lambda r: r[0], reverse=True)
    return [record for _, record in ranked], skipped_confidential


PUBLICATIONS_HEADER = """# GENERATED by tools/render_publications.py. Do not hand-edit.
# Source: personal/cv/publications.bib (+ _data/pub_extras.yml). Rendered by _pages/publications.html.
# Confidential unpublished work (keyword `inreview` or `working`, or any entry whose note mentions "under review")
# is excluded from this public data by design.
# Newest first; regenerate with bin/sync-publications.
"""


def render_publications_yaml(records: list[dict]) -> str:
    return PUBLICATIONS_HEADER + yaml.safe_dump(records, sort_keys=False, allow_unicode=True, width=1000)


def load_area_slugs() -> set[str]:
    return {a["slug"] for a in yaml.safe_load(AREAS_PATH.read_text())}


def load_type_ids() -> set[str]:
    return {t["id"] for t in yaml.safe_load(TYPES_PATH.read_text())}


def render_all(bib_path: Path) -> tuple[str, int]:
    """(publications.yml text, confidential entries dropped). Pure: writes nothing."""
    with open(bib_path) as f:
        db = bibtexparser.load(f)
    records, skipped_confidential = build_records(db.entries, load_extras(), load_area_slugs(), load_type_ids())
    return render_publications_yaml(records), skipped_confidential


def main():
    bib_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_BIB
    if not bib_path.exists():
        sys.exit(f"bib not found: {bib_path}")

    publications_yaml, skipped_confidential = render_all(bib_path)
    PUBLICATIONS_PATH.write_text(publications_yaml)
    print(f"Wrote {publications_yaml.count('- key:')} publications to {PUBLICATIONS_PATH}"
          f" ({skipped_confidential} confidential entries excluded)")


if __name__ == "__main__":
    main()
