source "https://rubygems.org"

# Hello! This is where you manage which Jekyll version is used to run.
# When you want to use a different version, change it below, save the
# file and run `bundle install`. Run Jekyll with `bundle exec`, like so:
#
#     bundle exec jekyll serve
#
# This will help ensure the proper Jekyll version is running.
# Happy Jekylling!

gem "github-pages", group: :jekyll_plugins

# If you want to use Jekyll native, uncomment the line below.
# To upgrade, run `bundle update`.

# gem "jekyll"

gem "wdm", "~> 0.1.0" if Gem.win_platform?

# Ruby 3.4+/4.x removed these from default gems; jekyll 3.9 / github-pages
# still expect them at runtime. Added for local dev only (not part of the
# server-side legacy Pages build, which pins its own ruby).
gem "csv"
gem "webrick"
gem "bigdecimal"
gem "base64"
gem "logger"
gem "ostruct"
gem "fiddle"

# If you have any plugins, put them here!
group :jekyll_plugins do
  # gem "jekyll-archives"
  gem "jekyll-feed"
  gem 'jekyll-sitemap'
end
