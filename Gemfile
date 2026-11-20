source "https://rubygems.org"

# Local preview and the test build. Production is GitHub's legacy Pages build, which uses its own pinned gem set and
# ignores this file and Gemfile.lock. The versions below are the ones github-pages 232 pins, so a local build
# predicts it. The `github-pages` metagem itself is deliberately not used: it pulls in ~100 gems (nokogiri,
# activesupport, rubyzip, ...) that never run for this site but raise Dependabot alerts on a lockfile nothing deploys.
gem "jekyll", "3.10.0"
gem "kramdown", "2.4.0"
gem "kramdown-parser-gfm", "1.1.0" # GFM input, set in _config.yml
gem "rouge", "3.30.0"
gem "liquid", "4.0.4"

group :jekyll_plugins do
  gem "jekyll-feed", "0.17.0"
  gem "jekyll-redirect-from", "0.16.0"
  gem "jekyll-sitemap", "1.4.0"
end

# Ruby 3.4+/4.x removed these from default gems; jekyll 3.10 still expects them at runtime.
gem "csv"
gem "webrick"
gem "bigdecimal"
gem "base64"
gem "logger"
gem "ostruct"
gem "fiddle"
