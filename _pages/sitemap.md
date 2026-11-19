---
layout: archive
title: "Sitemap"
permalink: /sitemap/
redirect_from:
  - /page-archive/
  - /collection-archive/
---

A list of all the pages and talks on the site. For you robots out there, an [XML version](/sitemap.xml) is available for digesting as well.

## Pages

<ul>
{% for p in site.pages %}{% if p.title and p.url != "/404.html" and p.url != "/sitemap/" and p.sitemap != false %}
  <li><a href="{{ p.url | relative_url }}">{{ p.title }}</a></li>
{% endif %}{% endfor %}
</ul>

## Talks

<ul>
{% for talk in site.talks reversed %}
  <li><a href="{{ talk.url | relative_url }}">{{ talk.title }}</a></li>
{% endfor %}
</ul>
