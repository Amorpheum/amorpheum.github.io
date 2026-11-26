"""Tests for tools/render_publications.py: ordering, the confidentiality filter and the published records.

Run: uv run --with 'bibtexparser<2' --with pyyaml python -m unittest discover -s tests -p 'test_*.py'
(stdlib unittest: the Ruby suite already gates the build, and pytest would be a new dependency.)
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import render_publications as rp  # noqa: E402


AREAS = {"care", "multimodal", "responsible-ai"}
TYPES = {"journal", "conference", "chapter", "extended", "preprint"}


def entry(key, year, month=None, **extra):
    e = {"ID": key, "author": "Choo, Kenny Tsu Wei", "title": f"Title {key}", "year": str(year),
         "booktitle": "Some Venue", "doi": f"10.1/{key}", "keywords": "conference"}
    if month is not None:
        e["month"] = month
    e.update(extra)
    return e


OLD = {"year": "2016", "type": "extended", "title": "Old paper", "authors": "Tan, A. and **Choo, K.T.W.**",
       "venue": "Some Workshop (2016)", "links": [{"label": "paper", "url": "/files/old.pdf"}]}


def records(entries, extras=None):
    recs, _ = rp.build_records(entries, extras or {}, AREAS, TYPES)
    return recs


def order(entries, extras=None):
    """Keys of the published entries, in page order."""
    return [r["key"] for r in records(entries, extras)]


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
        extras = {"extra_entries": [OLD]}
        recs = records([entry("new", 2026, "May"), entry("mid", 2018, "June")], extras)
        self.assertEqual([r["year"] for r in recs], [2026, 2018, 2016])
        self.assertEqual(recs[-1]["title"], "Old paper")


class ConfidentialityTest(unittest.TestCase):
    def test_inreview_keyword_and_under_review_note_never_render(self):
        entries = [
            entry("public", 2026, "May"),
            entry("kw", 2026, "June", keywords="inreview"),
            entry("kw2", 2026, "June", keywords="foo, InReview"),
            entry("note", 2026, "July", note="Under review at CHI"),
        ]
        recs, skipped = rp.build_records(entries, {}, AREAS, TYPES)
        self.assertEqual(order(entries), ["public"])
        self.assertEqual(skipped, 3)
        for secret in ("kw", "kw2", "note"):
            self.assertNotIn(f"Title {secret}", str(recs))
        self.assertNotIn("Title kw", rp.render_publications_yaml(recs))

    def test_working_keyword_never_renders_even_with_no_note(self):
        # `working` entries (unpublished, not submitted) carry no "under review" note, so the keyword is the only gate
        entries = [
            entry("public", 2026, "May"),
            entry("w1", 2026, "June", keywords="working"),
            entry("w2", 2026, "June", keywords="foo, Working"),
        ]
        recs, skipped = rp.build_records(entries, {}, AREAS, TYPES)
        self.assertEqual(order(entries), ["public"])
        self.assertEqual(skipped, 2)
        for secret in ("w1", "w2"):
            self.assertNotIn(f"Title {secret}", str(recs))
            self.assertNotIn(f"Title {secret}", rp.render_publications_yaml(recs))


class RecordTest(unittest.TestCase):
    """What each paper becomes in _data/publications.yml, which the page template renders."""

    def one(self, e, extras=None):
        (rec,) = records([e], extras)
        return rec

    def test_fields(self):
        rec = self.one(entry("k", 2026, "May", pages="1--5", address="Rome, Italy"))
        self.assertEqual(set(rec), {"key", "year", "type", "title", "authors", "venue", "note", "award", "areas", "links"})
        self.assertEqual((rec["key"], rec["year"], rec["title"]), ("k", 2026, "Title k"))
        self.assertEqual(rec["authors"], "**Choo, K.T.W.**")
        self.assertEqual(rec["venue"], "Some Venue (Rome, Italy, May 2026), 1\u20135")

    def test_venue_shows_the_article_number_before_the_pages(self):
        rec = self.one(entry("k", 2026, eid="CSCW108", pages="1--52"))
        self.assertEqual(rec["venue"], "Some Venue (2026), CSCW108, 1–52")

    def test_type_is_the_type_keyword_and_selected_is_not_a_type(self):
        self.assertEqual(self.one(entry("k", 2026, keywords="journal, selected"))["type"], "journal")
        self.assertEqual(self.one(entry("k", 2026, keywords="selected, preprint"))["type"], "preprint")

    def test_missing_double_or_unknown_type_is_an_error(self):
        for keywords in ("selected", "", "journal, conference", "poster"):
            with self.subTest(keywords=keywords), self.assertRaises(ValueError):
                records([entry("k", 2026, keywords=keywords)])

    def test_a_confidential_entry_needs_no_type(self):
        # it is dropped before anything is asked of it
        self.assertEqual(records([entry("k", 2026, keywords="inreview")]), [])
        self.assertEqual(records([entry("k", 2026, keywords="working")]), [])

    def test_areas_come_from_the_sidecar_and_default_to_other(self):
        extras = {"by_key": {"a": {"areas": ["care", "multimodal"]}}}
        self.assertEqual(self.one(entry("a", 2026), extras)["areas"], ["care", "multimodal"])
        self.assertEqual(self.one(entry("b", 2026), extras)["areas"], ["other"])

    def test_an_unknown_area_slug_is_an_error(self):
        with self.assertRaises(ValueError):
            records([entry("a", 2026)], {"by_key": {"a": {"areas": ["cares"]}}})

    def test_award_follows_a_bold_note(self):
        bold = self.one(entry("a", 2026, note="{\\textbf{Honourable Mention Award}}"))
        self.assertEqual((bold["award"], bold["note"]), (True, "Honourable Mention Award"))
        plain = self.one(entry("b", 2026, note="arXiv:2606.00028"))
        self.assertEqual((plain["award"], plain["note"]), (False, "arXiv:2606.00028"))
        none = self.one(entry("c", 2026))
        self.assertEqual((none["award"], none["note"]), (False, ""))

    def test_links_are_paper_then_video_then_dataset(self):
        extras = {"by_key": {"k": {"video": "https://v", "dataset": "https://d"}}}
        links = self.one(entry("k", 2026), extras)["links"]
        self.assertEqual(links, [{"label": "paper", "url": "https://doi.org/10.1/k"},
                                 {"label": "video", "url": "https://v"}, {"label": "dataset", "url": "https://d"}])

    def test_paper_link_falls_back_to_the_bib_url_then_the_sidecar_pdf(self):
        no_doi = entry("k", 2026, url="https://example.org/p")
        del no_doi["doi"]
        self.assertEqual(self.one(no_doi)["links"], [{"label": "paper", "url": "https://example.org/p"}])
        bare = entry("k", 2026)
        del bare["doi"]
        self.assertEqual(self.one(bare, {"by_key": {"k": {"pdf": "/files/k.pdf"}}})["links"],
                         [{"label": "paper", "url": "/files/k.pdf"}])

    def test_hand_carried_entries_are_structured_and_typed(self):
        rec = records([], {"extra_entries": [OLD]})[0]
        self.assertEqual(rec["type"], "extended")
        self.assertEqual(rec["areas"], ["other"])
        self.assertEqual(rec["links"], OLD["links"])
        self.assertFalse(rec["award"])

    def test_a_hand_carried_entry_without_a_known_type_is_an_error(self):
        for bad in ({k: v for k, v in OLD.items() if k != "type"}, {**OLD, "type": "poster"}):
            with self.assertRaises(ValueError):
                records([], {"extra_entries": [bad]})

    def test_yaml_round_trips(self):
        import yaml
        recs = records([entry("a", 2026, "May"), entry("b", 2025, "May")], {"extra_entries": [OLD]})
        self.assertEqual(yaml.safe_load(rp.render_publications_yaml(recs)), recs)


class SiteInStepWithBibTest(unittest.TestCase):
    """The CV's publications.bib is the source of truth; the generated site file must match it.

    Skipped when the bib is not on this machine. When it fails, run bin/sync-publications.
    """

    def test_generated_files_match_what_the_bib_produces_now(self):
        if not rp.DEFAULT_BIB.exists():
            self.skipTest(f"{rp.DEFAULT_BIB} not present")
        publications, _ = rp.render_all(rp.DEFAULT_BIB)
        hint = "out of step with the CV bib: run bin/sync-publications and review the diff"
        self.assertEqual(rp.PUBLICATIONS_PATH.read_text(), publications, f"_data/publications.yml {hint}")


if __name__ == "__main__":
    unittest.main()
