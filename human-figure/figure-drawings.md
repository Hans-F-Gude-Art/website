---
layout: default
title: Figure Drawings
galleries_data: figure_drawings_galleries
---

# Figure Drawings

<ul class="gallery-grid">
{% for item in site.data.figure_drawings_galleries %}
  <li>
    <a href="{{ item.url | relative_url }}">
      <img src="{{ item.image | relative_url }}" alt="{{ item.title }}">
      <h2>{{ item.title }}</h2>
    </a>
  </li>
{% endfor %}
</ul>
