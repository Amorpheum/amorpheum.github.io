require "minitest/autorun"
require "cgi"
require "fileutils"
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
  # tools/render_publications.py drops these; this is the second gate on what the page finally says.
  def test_publications_page_has_no_work_under_review
    refute_match(/under review|under submission|in review/i, text_of("/publications/"))
  end

  def test_publications_page_still_lists_the_papers
    assert_operator html_of("/publications/").scan("<li>").size, :>=, 40, "publication list looks truncated"
  end
end

class EmailTest < Minitest::Test
  # The address may sit in a mailto: link, never as visible text, and no other address may appear.
  def test_address_is_only_ever_inside_a_mailto_link
    built_pages.reject { |p| p.start_with?("talkmap/") }.each do |page|
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
    built_pages.reject { |p| p.start_with?("talkmap/") }.each do |page|
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
