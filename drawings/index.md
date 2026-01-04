---
layout: default
title: Drawings
galleries_data: drawings_galleries
---

# Drawings

<ul class="gallery-grid">
{% for item in site.data.drawings_galleries %}
  <li>
    <a href="{{ item.url | relative_url }}">
      <img src="{{ item.image | relative_url }}" alt="{{ item.title }}">
      <h2>{{ item.title }}</h2>
    </a>
  </li>
{% endfor %}
</ul>
