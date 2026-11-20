require "minitest/autorun"
require "cgi"
require "fileutils"
require "json"
require "open3"
require "tmpdir"
require "yaml"

ROOT = File.expand_path("..", __dir__)
LAB = File.expand_path("../cailab-website", ROOT) # canonical source of the design tokens and research areas

# One real build shared by every test; the build is the slow part.
BUILD = begin
  dest = Dir.mktmpdir("personal-page-")
  # after_run, not at_exit: autorun's own at_exit would otherwise fire second.
  Minitest.after_run { FileUtils.remove_entry(dest) }
  out, status = Open3.capture2e(
    "bundle", "exec", "jekyll", "build", "--strict_front_matter", "--destination", dest,
    chdir: ROOT
  )
  abort "jekyll build failed:\n#{out}" unless status.success?
  dest
end

def read(path) = File.read(File.join(ROOT, path))

# A permalink ending in "/" builds to <path>/index.html; one without builds to <path>.html (the talks).
def html_of(page)
  file = if page == "/" then "index.html"
         elsif page.end_with?("/") then File.join(page, "index.html")
         else "#{page}.html"
         end
  File.read(File.join(BUILD, file))
end

def text_of(page) = html_of(page).gsub(/<[^>]+>/, " ").gsub(/\s+/, " ")

# The Publications page, as [year, [row html, ...]] in page order: one <section id="YYYY"> per year, one
# <li class="publication-row"> per paper. (The nav and footer have their own <li>s, so rows are matched by class.)
def publication_sections
  html_of("/publications/").scan(%r{<section class="section section--year" id="(\d{4})">(.*?)</section>}m).map do |year, body|
    [year.to_i, body.scan(%r{<li class="publication-row".*?</li>}m)]
  end
end

def publication_rows = publication_sections.flat_map(&:last)
def row_title(row) = CGI.unescapeHTML(row[%r{<h3 class="publication-row__title">(.*?)</h3>}m, 1].to_s.gsub(/<[^>]+>/, ""))

# Every built HTML page, as a path relative to the build root.
def built_pages = Dir.glob("**/*.html", base: BUILD).sort

# A real address: letter-led domain and a 2+ letter TLD (the Google Fonts URL has "wght@12..96").
EMAIL = /[\w.+-]+@[A-Za-z][\w-]*(\.[A-Za-z][\w-]*)*\.[A-Za-z]{2,}/

def emails_in(str) = str.to_enum(:scan, EMAIL).map { Regexp.last_match[0] }

CONFIG = YAML.safe_load(read("_config.yml"))
CONTACT_ADDRESS = CONFIG.dig("author", "email")

# assert_includes dumps the whole page on failure; these keep the message short.
def assert_has(haystack, needle, msg) = assert(haystack.include?(needle), msg)
def refute_has(haystack, needle, msg) = refute(haystack.include?(needle), msg)

# Every URL that existed before the 2026-11 redesign still resolves. The list was taken from a build of the old
# site; theme internals (compiled theme CSS and JS, demo listings) are deliberately not part of it.
class UrlContractTest < Minitest::Test
  def test_every_old_path_is_still_built
    expected = read("tests/expected_paths.txt").split("\n")
    missing = expected.reject { |p| File.exist?(File.join(BUILD, p)) }
    assert_empty missing, "paths from the old site are gone"
  end
end

# The production host is named in CNAME (what GitHub Pages serves) and mirrored in _config.yml `url:`.
class ProductionIdentityTest < Minitest::Test
  CNAME_HOST = read("CNAME").strip
  ORIGIN = "https://#{CNAME_HOST}".freeze

  def test_cname_names_the_production_host_and_is_published
    assert_equal "kennychoo.net", CNAME_HOST
    assert_equal CNAME_HOST, File.read(File.join(BUILD, "CNAME")).strip, "CNAME missing from the built site"
  end

  def test_config_url_matches_the_cname_host
    assert_equal ORIGIN, CONFIG["url"]
  end

  def test_home_has_canonical_and_sharing_tags_on_production_origin
    html = html_of("/")
    assert_equal "#{ORIGIN}/", html[/<link rel="canonical" href="([^"]+)"/, 1]
    assert_equal "#{ORIGIN}/", html[/<meta property="og:url" content="([^"]+)"/, 1]
    assert_match(/<meta property="og:title" content="[^"]+"/, html)
    assert_match(%r{<meta property="og:image" content="#{Regexp.escape(ORIGIN)}/[^"]+"}, html)
  end

  # A local preview must not quietly load production assets (the old theme prepended site.url to them).
  def test_stylesheet_and_scripts_are_relative_so_a_local_preview_shows_local_files
    html = html_of("/")
    refute_match(%r{(?:href|src)="https://kennychoo\.net/assets}, html)
    assert_has html, 'href="/assets/css/site.css"', "stylesheet link"
  end
end

class PublicContentTest < Minitest::Test
  # tools/render_publications.py drops these; this is the second gate on what the page finally says.
  def test_publications_page_has_no_work_under_review
    refute_match(/under review|under submission|in review/i, text_of("/publications/"))
  end

  def test_publications_page_still_lists_the_papers
    assert_operator publication_rows.size, :>=, 45, "publication list looks truncated"
  end

  def test_every_generated_record_is_on_the_page_once
    keys = YAML.safe_load(read("_data/publications.yml")).map { |r| r["title"] }
    assert_equal keys.size, publication_rows.size
    assert_equal keys.map { |t| t.downcase.gsub(/[^a-z0-9]/, "") }.sort,
                 publication_rows.map { |r| row_title(r).downcase.gsub(/[^a-z0-9]/, "") }.sort
  end

  def test_years_are_newest_first_and_each_appears_once
    years = publication_sections.map(&:first)
    refute_empty years
    assert_equal years.uniq.sort.reverse, years, "year sections are out of order or repeated"
    publication_sections.each { |year, rows| refute_empty rows, "empty section #{year}" }
  end

  # The CAILab list is maintained separately; a paper it shows must not be missing here.
  def test_every_paper_on_the_lab_site_is_listed
    lab_file = File.join(LAB, "_data/publications.yml")
    skip "sibling cailab-website not present" unless File.exist?(lab_file)
    squash = ->(str) { CGI.unescapeHTML(str.gsub(/<[^>]+>/, " ")).downcase.gsub(/[^a-z0-9]/, "") }
    page = squash.call(publication_rows.join)
    missing = YAML.safe_load(File.read(lab_file)).map { |p| p["title"] }.reject { |t| page.include?(squash.call(t)) }
    assert_empty missing, "on the lab site but not on this page"
  end
end

# The lab list and the CV bib are kept separately; they once disagreed on a paper's year (InfoTrace, Gaze Patterns).
class PublicationYearsAgreeWithLabTest < Minitest::Test
  def test_every_paper_is_filed_under_the_year_the_lab_site_gives_it
    lab_file = File.join(LAB, "_data/publications.yml")
    skip "sibling cailab-website not present" unless File.exist?(lab_file)
    squash = ->(str) { str.downcase.gsub(/[^a-z0-9]/, "") }
    filed = publication_sections.flat_map { |year, rows| rows.map { |row| [squash.call(row_title(row)), year] } }
    mismatches = YAML.safe_load(File.read(lab_file)).filter_map do |paper|
      printed = filed.find { |title, _| title == squash.call(paper["title"]) }&.last
      "#{paper["title"]}: lab #{paper["year"]}, here #{printed}" if printed && printed != paper["year"].to_i
    end
    assert_empty mismatches, "year differs between the lab site and the CV bib (fix the bib, then bin/sync-publications)"
  end
end

# The year folds, the filter bar and the labels (assets/js/year-folds.js reveals and drives them; the markup must
# work without it).
class PublicationsPageTest < Minitest::Test
  TYPES = YAML.safe_load(read("_data/publication_types.yml")).map { |t| t["id"] }.freeze
  AREAS = (YAML.safe_load(read("_data/areas.yml")).map { |a| a["slug"] } + ["other"]).freeze

  def test_only_the_newest_year_starts_open
    html = html_of("/publications/")
    assert_equal 1, html.scan(%r{<details class="year"[^>]*\bopen\b}).size
    assert_match(%r{<section class="section section--year" id="#{publication_sections.first.first}">\s*<div class="container">\s*<details class="year" open>}m, html)
  end

  def test_every_row_has_a_known_type_known_areas_and_search_text
    publication_rows.each do |row|
      type = row[/data-type="([^"]+)"/, 1]
      assert_includes TYPES, type, "type on #{row_title(row)}"
      areas = row[/data-areas="([^"]+)"/, 1].to_s.split
      refute_empty areas, "no areas on #{row_title(row)}"
      assert_empty areas - AREAS, "unknown area on #{row_title(row)}"
      assert_match(/data-text="[^"]+"/, row, "search text on #{row_title(row)}")
      assert_has row, %(<span class="pill pill--type">), "type pill on #{row_title(row)}"
    end
  end

  def test_area_pills_match_the_rows_areas
    publication_rows.each do |row|
      pills = row.scan(/class="pill pill--area a\d" data-area="([^"]+)"/).flatten
      areas = row[/data-areas="([^"]+)"/, 1].split - ["other"]
      assert_equal areas, pills, "pills vs data-areas on #{row_title(row)}"
    end
  end

  # Without JS the controls would be dead, so they start hidden and year-folds.js reveals them.
  def test_filter_bar_starts_hidden_and_has_a_chip_for_each_used_type_and_every_area
    html = html_of("/publications/")
    assert_match(/<div class="container pub-filters" hidden>/, html)
    used = publication_rows.map { |r| r[/data-type="([^"]+)"/, 1] }.uniq
    assert_equal used.sort, html.scan(/data-filter="type" data-value="([^"]+)"/).flatten.sort
    assert_equal AREAS.sort, html.scan(/data-filter="area" data-value="([^"]+)"/).flatten.sort
  end

  def test_the_script_is_loaded_here_published_and_not_on_other_pages
    assert File.exist?(File.join(BUILD, "assets/js/year-folds.js")), "year-folds.js not published"
    assert_has html_of("/publications/"), 'src="/assets/js/year-folds.js"', "script on /publications/"
    refute_has html_of("/"), "year-folds.js", "script leaked onto the home page"
  end

  def test_award_papers_carry_the_medal_and_nothing_else_does
    medals = publication_rows.select { |r| r.include?("class=\"medal\"") }
    awards = YAML.safe_load(read("_data/publications.yml")).select { |r| r["award"] }.map { |r| r["title"] }
    assert_equal awards.sort, medals.map { |r| row_title(r) }.sort
    refute_empty awards
  end

  def test_every_row_has_links_and_every_bib_paper_an_anchor_for_deep_links
    publication_rows.each { |row| assert_has row, 'class="publication-row__links"', "links on #{row_title(row)}" }
    keyed = YAML.safe_load(read("_data/publications.yml")).map { |r| r["key"] }.reject(&:empty?)
    anchors = publication_rows.filter_map { |r| r[/<li class="publication-row" id="pub-([^"]+)"/, 1] }.map { |a| CGI.unescapeHTML(a) }
    assert_equal keyed.sort, anchors.sort, "#pub-<key> anchors (the lab's research cards link to them)"
  end

  def test_the_hidden_attribute_wins_over_component_display_rules
    assert_has read("assets/css/site.css"), "[hidden]{display:none!important}", "hidden rule"
  end
end

# The lab owns the classification, areas and filter script; these are copies, so a change there is copied here.
class PublicationsAgreeWithLabTest < Minitest::Test
  def lab(path) = File.join(LAB, path)

  def test_publication_types_equal_the_labs
    skip "sibling cailab-website not present" unless File.exist?(lab("_data/publication_types.yml"))
    assert_equal YAML.safe_load(File.read(lab("_data/publication_types.yml"))), YAML.safe_load(read("_data/publication_types.yml"))
  end

  def test_area_colours_equal_the_labs
    skip "sibling cailab-website not present" unless File.exist?(lab("_data/research.yml"))
    lab_areas = YAML.safe_load(File.read(lab("_data/research.yml")))["areas"]
    mine = YAML.safe_load(read("_data/areas.yml"))
    assert_equal lab_areas.map { |a| [a["slug"], a["short"], a["pastel"]] }, mine.map { |a| [a["slug"], a["short"], a["pastel"]] }
  end

  def test_filter_script_equals_the_labs
    skip "sibling cailab-website not present" unless File.exist?(lab("assets/js/year-folds.js"))
    mine = read("assets/js/year-folds.js").sub(/\A(\/\/[^\n]*\n){2}/, "")
    assert_equal File.read(lab("assets/js/year-folds.js")), mine
  end

  # pub_extras.yml `areas` is a copy of research.yml's papers/more lists, matched by title.
  def test_paper_areas_equal_the_labs_by_title
    skip "sibling cailab-website not present" unless File.exist?(lab("_data/research.yml"))
    squash = ->(str) { str.downcase.gsub(/[^a-z0-9]/, "") }
    research = YAML.safe_load(File.read(lab("_data/research.yml")))["areas"]
    lab_pubs = YAML.safe_load(File.read(lab("_data/publications.yml"))).to_h { |p| [p["id"], squash.call(p["title"])] }
    expected = Hash.new { |h, k| h[k] = [] }
    research.each { |a| (a["papers"] + a["more"]).uniq.each { |id| expected[lab_pubs.fetch(id)] << a["slug"] } }
    mine = YAML.safe_load(read("_data/publications.yml")).to_h { |r| [squash.call(r["title"]), r["areas"] - ["other"]] }
    wrong = expected.filter_map do |title, slugs|
      "#{title[0, 40]}: lab #{slugs}, here #{mine[title].inspect}" if mine.key?(title) && mine[title].sort != slugs.sort
    end
    assert_empty wrong, "research areas differ from the lab site"
    extra = mine.reject { |t, a| a.empty? || expected.key?(t) }.keys
    assert_empty extra, "a paper has areas here that the lab does not give it"
  end
end

class EmailTest < Minitest::Test
  # The address may sit in a mailto: link, never as visible text, and no other address may appear.
  def test_address_is_only_ever_inside_a_mailto_link
    built_pages.each do |page|
      html = File.read(File.join(BUILD, page))
      assert_empty emails_in(html) - [CONTACT_ADDRESS], "unexpected address in #{page}"
      visible = html.gsub(/<script.*?<\/script>/m, " ").gsub(/<[^>]+>/, " ")
      assert_empty emails_in(visible), "address shown as text in #{page}"
    end
  end

  def test_every_main_page_offers_the_mailto_button
    %w[/ /publications/ /talks/ /teaching/ /service/ /cv/].each do |page|
      assert_has html_of(page), %(href="mailto:#{CONTACT_ADDRESS}"), "#{page} has no mail link"
    end
  end
end

class DesignLanguageTest < Minitest::Test
  def test_old_theme_is_gone_from_every_page
    built_pages.each do |page|
      html = File.read(File.join(BUILD, page))
      %w[main.css main.min.js font-awesome fontawesome academicons author__avatar].each do |leftover|
        refute_has html, leftover, "#{page} still references #{leftover}"
      end
    end
  end

  # The lab's site.css is canonical; the tokens are copied, so a change there must be copied here too.
  def test_root_tokens_match_the_lab_stylesheet
    skip "sibling cailab-website not present" unless File.exist?(File.join(LAB, "assets/css/site.css"))
    root = ->(css) { css[/:root\{.*?\n\}/m] }
    mine = root.call(read("assets/css/site.css"))
    refute_nil mine, "no :root block in assets/css/site.css"
    assert_equal root.call(File.read(File.join(LAB, "assets/css/site.css"))), mine
  end

  def test_stylesheet_names_its_source
    assert_has read("assets/css/site.css")[0, 600], "cailab-website/assets/css/site.css", "provenance header"
  end
end

class HomePageTest < Minitest::Test
  def test_hero_is_a_name_seeded_ring_around_the_photo_with_alt_text
    html = html_of("/")
    assert_match(/<svg[^>]*data-ring="Kenny Tsu Wei Choo"/, html)
    assert_match(%r{<img[^>]*src="/images/kennychoo\.png"[^>]*alt="[^"]+"}, html)
  end

  def test_hero_links_out_to_the_profiles_and_the_lab
    html = html_of("/")
    [CONFIG.dig("author", "googlescholar"), CONFIG.dig("author", "orcid"),
     "https://github.com/#{CONFIG.dig("author", "github")}", "https://www.cailab.info"].each do |url|
      assert_has html, %(href="#{url}"), "home lacks a link to #{url}"
    end
  end

  def test_lists_each_research_area_with_its_link_into_the_lab_site
    areas = YAML.safe_load(read("_data/areas.yml"))
    assert_equal 3, areas.size
    areas.each do |a|
      assert_has html_of("/"), %(href="https://www.cailab.info/research/##{a["slug"]}"), "tile for #{a["slug"]}"
      assert_has text_of("/"), a["title"], "title #{a["title"]}"
    end
  end

  # lab/_data/research.yml is canonical for the areas (see CLAUDE.md).
  def test_areas_match_the_labs_research_areas
    lab_file = File.join(LAB, "_data/research.yml")
    skip "sibling cailab-website not present" unless File.exist?(lab_file)
    lab = YAML.safe_load(File.read(lab_file))["areas"]
    mine = YAML.safe_load(read("_data/areas.yml"))
    assert_equal lab.map { |a| [a["slug"], a["title"]] }, mine.map { |a| [a["slug"], a["title"]] }
  end

  def test_shows_the_three_newest_talks_and_links_to_all
    html = html_of("/")
    assert_has html, 'href="/talks/"', "link to all talks"
    assert_equal 3, html.scan(/class="news-item\b/).size
  end
end

# Template and theme leftovers that the redesign left published. Several said things that were false for this site
# (cookies, analytics, a talk map of someone else's talks). Removing one is deliberate, so each is named here and
# dropped from tests/expected_paths.txt.
class LeftoversTest < Minitest::Test
  GONE = %w[terms talkmap talkmap.html talkmap.py talkmap.ipynb markdown_generator CONTRIBUTING.md
            images/site-logo.png images/manifest.json images/browserconfig.xml images/safari-pinned-tab.svg].freeze

  def test_template_leftovers_are_not_published
    present = GONE.select { |p| File.exist?(File.join(BUILD, p)) }
    present += Dir.glob("images/mstile-*", base: BUILD)
    assert_empty present, "still published"
  end

  def test_sitemap_lists_none_of_the_removed_pages
    xml = File.read(File.join(BUILD, "sitemap.xml"))
    %w[/terms /talkmap /markdown_generator /CONTRIBUTING].each { |path| refute_has xml, path, "sitemap still lists #{path}" }
  end

  # Nothing may name a theme, a comment system or an analytics product the site does not use.
  def test_no_published_file_mentions_the_theme_or_unused_services
    offenders = Dir.glob("**/*.{html,xml,json,txt,js,css,md}", base: BUILD).select do |f|
      File.read(File.join(BUILD, f)).match?(/minimal.?mistakes|mmistakes|academicpages|disqus|google.?analytics/i)
    end
    assert_empty offenders
  end
end

class IconTest < Minitest::Test
  def icon_hrefs(html) = html.scan(/<link rel="(?:icon|apple-touch-icon)"[^>]*href="([^"]+)"/).flatten

  def test_head_declares_icons_and_every_one_is_published
    hrefs = icon_hrefs(html_of("/"))
    assert_operator hrefs.size, :>=, 2, "expected an icon and an apple-touch-icon"
    hrefs.each { |h| assert File.exist?(File.join(BUILD, h.split("?").first)), "icon #{h} is not published" }
  end

  # Browsers ask for /favicon.ico whatever the page says.
  def test_favicon_ico_is_a_real_ico_file
    ico = File.binread(File.join(BUILD, "favicon.ico"))
    assert_equal [0, 0, 1, 0], ico.bytes.first(4), "not an ICO header"
  end

  def test_apple_touch_icon_is_a_180px_png
    href = icon_hrefs(html_of("/")).find { |h| h.include?("apple-touch") }
    refute_nil href, "no apple-touch-icon link"
    png = File.binread(File.join(BUILD, href))
    assert_equal "\x89PNG".b, png[0, 4]
    assert_equal [180, 180], png[16, 8].unpack("NN")
  end
end

class FeedTest < Minitest::Test
  FEED = File.join(BUILD, "feed.xml")

  def test_advertised_feed_is_feed_xml_in_head_and_footer
    html = html_of("/")
    assert_equal "/feed.xml", html[/<link rel="alternate" type="application\/atom\+xml"[^>]*href="([^"]+)"/, 1]
    assert_has html, 'href="/feed.xml">Feed</a>', "footer feed link"
  end

  def test_feed_has_an_entry_for_every_talk_on_the_production_host
    entries = File.read(FEED).scan(%r{<entry>.*?</entry>}m)
    assert_equal Dir.glob("_talks/*.md", base: ROOT).size, entries.size
    entries.each { |e| assert_match(%r{<link href="https://kennychoo\.net/talks/}, e) }
  end
end

class StructuredDataTest < Minitest::Test
  def person
    json = html_of("/")[%r{<script type="application/ld\+json">(.*?)</script>}m, 1]
    refute_nil json, "no JSON-LD on the home page"
    JSON.parse(json)
  end

  def test_home_describes_the_owner_as_a_person_with_profiles
    p = person
    assert_equal "Person", p["@type"]
    assert_equal CONFIG.dig("author", "name"), p["name"]
    assert_equal "https://kennychoo.net/", p["url"]
    assert_match(/SUTD|Singapore University of Technology and Design/, p.dig("affiliation", "name"))
    [CONFIG.dig("author", "googlescholar"), CONFIG.dig("author", "orcid"),
     "https://github.com/#{CONFIG.dig("author", "github")}", "https://www.cailab.info"].each do |url|
      assert_includes p["sameAs"], url
    end
  end

  # The contact address stays out of visible text and metadata; only the mailto: button carries it.
  def test_json_ld_does_not_carry_the_email_address
    refute_has html_of("/")[%r{<script type="application/ld\+json">.*?</script>}m].to_s, CONTACT_ADDRESS, "email in JSON-LD"
  end
end

class SelectedPublicationsTest < Minitest::Test
  def squash(str) = CGI.unescapeHTML(str.gsub(/<[^>]+>/, " ")).downcase.gsub(/[^a-z0-9]/, "")
  def selected = YAML.safe_load(read("_data/selected_pubs.yml"))

  def test_home_lists_each_selected_paper_and_links_to_all_publications
    html = html_of("/")
    assert_has html, 'href="/publications/"', "link to all publications"
    refute_empty selected
    page = squash(html)
    selected.each do |s|
      title = s["citation"][/\[(.*?)\]\(/m, 1]
      assert page.include?(squash(title)), "selected paper missing from home: #{title}"
    end
  end

  def test_every_selected_paper_is_also_on_the_publications_page
    page = squash(publication_rows.join)
    selected.each { |s| assert page.include?(squash(s["citation"][/\[(.*?)\]\(/m, 1])), "not on publications page: #{s["key"]}" }
  end

  def test_home_shows_no_work_under_review
    refute_match(/under review|under submission|in review/i, text_of("/"))
  end

  # Scoped to the section: the research-area text on the same page already mentions the awards.
  def test_the_award_papers_are_visible_in_the_publications_section
    section = html_of("/")[%r{<section[^>]*id="publications".*?</section>}m]
    refute_nil section, "no publications section on home"
    assert_has section, "Honourable Mention", "award note"
  end
end

class CvPageTest < Minitest::Test
  # The course list lives on /teaching/ alone; a copy here had already drifted (no XR, no GenAI course).
  def test_cv_links_to_teaching_instead_of_repeating_the_course_list
    assert_has html_of("/cv/"), 'href="/teaching/"', "link to the teaching page"
    refute_has text_of("/cv/"), "Computation Structures", "course list copied into the CV page"
  end
end

class NavTest < Minitest::Test
  PAGES = %w[/ /publications/ /talks/ /teaching/ /service/ /cv/].freeze

  # On a phone the links collapse behind a Menu button. The button starts `hidden` and nav.js reveals it, so a
  # visitor without JS gets the plain links and never a dead button.
  def test_every_page_has_a_hidden_menu_button_wired_to_the_link_list
    PAGES.each do |page|
      html = html_of(page)
      button = html[/<button[^>]*class="nav__toggle"[^>]*>/]
      refute_nil button, "no menu button on #{page}"
      assert_match(/aria-expanded="false"/, button, "closed at load on #{page}")
      assert_match(/\bhidden\b/, button, "button must start hidden on #{page}")
      target = button[/aria-controls="([^"]+)"/, 1]
      refute_nil target, "button controls nothing on #{page}"
      assert_match(/<ul[^>]*id="#{Regexp.escape(target)}"/, html, "no list with id #{target} on #{page}")
    end
  end

  def test_every_page_loads_the_menu_script_and_it_is_published
    assert File.exist?(File.join(BUILD, "assets/js/nav.js")), "nav.js not published"
    PAGES.each { |page| assert_has html_of(page), 'src="/assets/js/nav.js"', "nav.js on #{page}" }
  end

  def test_links_stay_in_the_markup_for_visitors_without_js
    expected = YAML.safe_load(read("_data/navigation.yml"))["main"].map { |i| i["url"] }
    PAGES.each do |page|
      list = html_of(page)[%r{<ul[^>]*id="nav-links".*?</ul>}m]
      refute_nil list, "no link list on #{page}"
      assert_equal expected, list.scan(/<a href="([^"]+)"/).flatten, "nav links on #{page}"
    end
  end
end

class PagesTest < Minitest::Test
  PAGES = %w[/ /publications/ /talks/ /teaching/ /teaching/teaching-statement/ /teaching/hciandai/ /cv/ /service/
             /talks/2026-09-23-nie-parent-child-ai].freeze

  def test_every_page_has_a_title_nav_and_the_shared_stylesheet
    PAGES.each do |page|
      html = html_of(page)
      assert_match(%r{<title>[^<]+</title>}, html, "title on #{page}")
      assert_has html, 'aria-label="Main"', "nav on #{page}"
      assert_has html, "/assets/css/site.css", "stylesheet on #{page}"
    end
  end

  def test_no_unrendered_template_syntax
    PAGES.each { |page| refute html_of(page).match?(/\{\{|\{%/), "unrendered Liquid on #{page}" }
  end

  def test_internal_links_resolve
    PAGES.each do |page|
      html_of(page).scan(/href="([^"]+)"/).flatten.map { |h| CGI.unescapeHTML(h) }.each do |href|
        next if href.start_with?("http", "mailto:", "#")
        path = href.split("#").first
        next if path.empty?
        target = File.join(BUILD, path.end_with?("/") ? File.join(path, "index.html") : path)
        target = "#{target}.html" if !File.exist?(target) && File.exist?("#{target}.html") # Pages serves /x as x.html
        assert File.exist?(target), "#{page}: dead link #{href}"
      end
    end
  end
end
