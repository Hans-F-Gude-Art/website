---
layout: default
title: Artwork by Medium
galleries_data: by_medium_galleries
---

# Artwork by Medium

<ul class="gallery-grid">
{% for item in site.data.by_medium_galleries %}
  <li>
    <a href="{{ item.url | relative_url }}">
      <img src="{{ item.image | relative_url }}" alt="{{ item.title }}">
      <h2>{{ item.title }}</h2>
    </a>
  </li>
{% endfor %}
</ul>
