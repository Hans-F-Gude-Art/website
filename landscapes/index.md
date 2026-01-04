---
layout: default
title: Landscapes
galleries_data: landscapes_galleries
---

# Landscape Artwork

<ul class="gallery-grid">
{% for item in site.data.landscapes_galleries %}
  <li>
    <a href="{{ item.url | relative_url }}">
      <img src="{{ item.image | relative_url }}" alt="{{ item.title }}">
      <h2>{{ item.title }}</h2>
    </a>
  </li>
{% endfor %}
</ul>
