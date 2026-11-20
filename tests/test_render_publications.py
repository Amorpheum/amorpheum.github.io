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


class SelectedTest(unittest.TestCase):
    """The home page shows the bib's `selected` entries (the same ones the 1-page CV uses)."""

    def keys(self, entries, extras=None):
        items, _ = rp.build_selected(entries, extras or {})
        return [i["citation"].split("[Title ")[1].split("]")[0] for i in items]

    def test_only_entries_keyworded_selected_are_chosen(self):
        entries = [entry("a", 2026, "May", keywords="conference, selected"), entry("b", 2026, "June"),
                   entry("c", 2025, "May", keywords="journal, Selected")]
        self.assertEqual(self.keys(entries), ["a", "c"])

    def test_keyword_must_match_exactly(self):
        entries = [entry("x", 2026, "May", keywords="preselected"), entry("y", 2026, "May", keywords="unselected, selected-ish")]
        self.assertEqual(self.keys(entries), [])

    def test_newest_first_like_the_publications_page(self):
        entries = [entry("old", 2019, "May", keywords="selected"), entry("new", 2026, "April", keywords="selected"),
                   entry("mid", 2023, "August", keywords="selected")]
        self.assertEqual(self.keys(entries), ["new", "mid", "old"])

    def test_confidential_work_is_never_selected(self):
        # the second path to a public page must go through the same filter as the publications page
        entries = [entry("ok", 2026, "May", keywords="selected"),
                   entry("kw", 2026, "June", keywords="inreview, selected"),
                   entry("note", 2026, "July", keywords="selected", note="Under review at CHI")]
        items, dropped = rp.build_selected(entries, {})
        self.assertEqual([i["citation"].split("[Title ")[1].split("]")[0] for i in items], ["ok"])
        self.assertEqual(dropped, 2)
        self.assertNotIn("Title kw", str(items))
        self.assertNotIn("Title note", str(items))

    def test_each_selected_citation_is_a_line_of_the_publications_page(self):
        entries = [entry("a", 2026, "May", keywords="selected", note="{\\textbf{Honourable Mention}}"),
                   entry("b", 2025, "May")]
        body, _ = rp.build_body(entries, {})
        items, _ = rp.build_selected(entries, {})
        self.assertEqual(len(items), 1)
        self.assertIn("1. " + items[0]["citation"], body.splitlines())

    def test_yaml_output_round_trips(self):
        import yaml
        items, _ = rp.build_selected([entry("a", 2026, "May", keywords="selected")], {})
        loaded = yaml.safe_load(rp.render_selected_yaml(items))
        self.assertEqual(loaded, items)
        self.assertEqual(set(loaded[0]), {"key", "year", "citation"})


class SiteInStepWithBibTest(unittest.TestCase):
    """The CV's publications.bib is the source of truth; the generated site files must match it.

    Skipped when the bib is not on this machine. When it fails, run bin/sync-publications.
    """

    def test_generated_files_match_what_the_bib_produces_now(self):
        if not rp.DEFAULT_BIB.exists():
            self.skipTest(f"{rp.DEFAULT_BIB} not present")
        page, selected, _, _ = rp.render_all(rp.DEFAULT_BIB)
        hint = "out of step with the CV bib: run bin/sync-publications and review the diff"
        self.assertEqual(rp.OUTPUT_PATH.read_text(), page, f"_pages/publications.md {hint}")
        self.assertEqual(rp.SELECTED_PATH.read_text(), selected, f"_data/selected_pubs.yml {hint}")


if __name__ == "__main__":
    unittest.main()
