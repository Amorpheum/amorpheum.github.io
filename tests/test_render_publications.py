"""Tests for tools/render_publications.py: ordering and the confidentiality filter.

Run: uv run --with 'bibtexparser<2' --with pyyaml python -m unittest discover -s tests -p 'test_*.py'
(stdlib unittest: the Ruby suite already gates the build, and pytest would be a new dependency.)
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import render_publications as rp  # noqa: E402


def entry(key, year, month=None, **extra):
    e = {"ID": key, "author": "Choo, Kenny Tsu Wei", "title": f"Title {key}", "year": str(year),
         "booktitle": "Some Venue", "doi": f"10.1/{key}"}
    if month is not None:
        e["month"] = month
    e.update(extra)
    return e


def order(entries, extras=None):
    """Keys of the rendered entries, in page order."""
    body, _ = rp.build_body(entries, extras or {})
    return [line.split("[Title ")[1].split("]")[0] for line in body.splitlines()]


class MonthNumberTest(unittest.TestCase):
    def test_full_names_abbreviations_and_case(self):
        self.assertEqual(rp.month_number("September"), 9)
        self.assertEqual(rp.month_number("Oct"), 10)
        self.assertEqual(rp.month_number("feb"), 2)
        self.assertEqual(rp.month_number("MARCH"), 3)

    def test_blank_or_unknown_is_zero(self):
        self.assertEqual(rp.month_number(""), 0)
        self.assertEqual(rp.month_number(None), 0)
        self.assertEqual(rp.month_number("Smarch"), 0)


class OrderTest(unittest.TestCase):
    def test_newest_month_first_within_a_year(self):
        # bib order is deliberately not chronological
        entries = [entry("apr", 2026, "April"), entry("sep", 2026, "September"), entry("mar", 2026, "March")]
        self.assertEqual(order(entries), ["sep", "apr", "mar"])

    def test_year_outranks_month(self):
        entries = [entry("dec25", 2025, "December"), entry("jan26", 2026, "January")]
        self.assertEqual(order(entries), ["jan26", "dec25"])

    def test_abbreviated_and_full_month_names_sort_together(self):
        entries = [entry("a", 2025, "Oct"), entry("b", 2025, "November"), entry("c", 2025, "june")]
        self.assertEqual(order(entries), ["b", "a", "c"])

    def test_equal_dates_keep_bib_order(self):
        entries = [entry("first", 2026, "April"), entry("second", 2026, "April")]
        self.assertEqual(order(entries), ["first", "second"])

    def test_entry_without_month_or_date_sorts_last_in_its_year(self):
        entries = [entry("nomonth", 2026), entry("mar", 2026, "March"), entry("dec25", 2025, "December")]
        self.assertEqual(order(entries), ["mar", "nomonth", "dec25"])

    def test_sidecar_date_places_an_entry_with_no_month(self):
        entries = [entry("mar", 2026, "March"), entry("nomonth", 2026), entry("sep", 2026, "September")]
        extras = {"by_key": {"nomonth": {"date": "2026-06"}}}
        self.assertEqual(order(entries, extras), ["sep", "nomonth", "mar"])

    def test_sidecar_date_overrides_the_bib_month(self):
        entries = [entry("a", 2026, "April"), entry("b", 2026, "April")]
        extras = {"by_key": {"b": {"date": "2026-03-06"}, "a": {"date": "2026-04-13"}}}
        self.assertEqual(order(entries, extras), ["a", "b"])
        self.assertEqual(order(list(reversed(entries)), extras), ["a", "b"])

    def test_sidecar_date_in_another_year_is_an_error(self):
        # the page prints the bib year, so an override that moved the entry across years would look out of order
        with self.assertRaises(ValueError):
            order([entry("x", 2025, "March")], {"by_key": {"x": {"date": "2024-12-16"}}})

    def test_hand_carried_entries_slot_in_by_year(self):
        extras = {"extra_entries": [{"year": "2016", "line": "1. Old paper 2016."}]}
        body, _ = rp.build_body([entry("new", 2026, "May"), entry("mid", 2018, "June")], extras)
        lines = body.splitlines()
        self.assertEqual(len(lines), 3)
        self.assertIn("Old paper", lines[-1])


class ConfidentialityTest(unittest.TestCase):
    def test_inreview_keyword_and_under_review_note_never_render(self):
        entries = [
            entry("public", 2026, "May"),
            entry("kw", 2026, "June", keywords="inreview"),
            entry("kw2", 2026, "June", keywords="foo, InReview"),
            entry("note", 2026, "July", note="Under review at CHI"),
        ]
        body, skipped = rp.build_body(entries, {})
        self.assertEqual(order(entries), ["public"])
        self.assertEqual(skipped, 3)
        for secret in ("kw", "kw2", "note"):
            self.assertNotIn(f"Title {secret}", body)


if __name__ == "__main__":
    unittest.main()
