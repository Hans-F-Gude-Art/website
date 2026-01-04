---
layout: default
title: Human Figure
galleries_data: figure_galleries
---

# Human Figure Artwork

<ul class="gallery-grid">
{% for item in site.data.figure_galleries %}
  <li>
    <a href="{{ item.url | relative_url }}">
      <img src="{{ item.image | relative_url }}" alt="{{ item.title }}">
      <h2>{{ item.title }}</h2>
    </a>
  </li>
{% endfor %}
</ul>
