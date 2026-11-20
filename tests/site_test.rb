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
  # The papers are the one <ol> in the page body; the nav and footer have their own <li>s.
  def publication_items = html_of("/publications/")[%r{<ol>.*?</ol>}m].scan(%r{<li>(.*?)</li>}m).flatten

  # tools/render_publications.py drops these; this is the second gate on what the page finally says.
  def test_publications_page_has_no_work_under_review
    refute_match(/under review|under submission|in review/i, text_of("/publications/"))
  end

  def test_publications_page_still_lists_the_papers
    assert_operator publication_items.size, :>=, 45, "publication list looks truncated"
  end

  def test_publications_are_newest_first_by_printed_year
    years = publication_items.map { |li| li[/ (\d{4})\. /, 1].to_i }
    refute_includes years, 0, "an entry has no year"
    assert_equal years.sort.reverse, years, "publication years are out of order"
  end

  # The CAILab list is maintained separately; a paper it shows must not be missing here.
  def test_every_paper_on_the_lab_site_is_listed
    lab_file = File.join(LAB, "_data/publications.yml")
    skip "sibling cailab-website not present" unless File.exist?(lab_file)
    squash = ->(str) { CGI.unescapeHTML(str.gsub(/<[^>]+>/, " ")).downcase.gsub(/[^a-z0-9]/, "") }
    page = squash.call(html_of("/publications/"))
    missing = YAML.safe_load(File.read(lab_file)).map { |p| p["title"] }.reject { |t| page.include?(squash.call(t)) }
    assert_empty missing, "on the lab site but not on this page"
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
    page = squash(html_of("/publications/"))
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
