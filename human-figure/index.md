---
layout: default
title: Human Figure
---

# Human Figure Artwork

<ul class="gallery-grid">
{% for item in site.data.figure_galleries %}
  <li>
    <a href="{{ item.url | relative_url }}">
      <img src="/assets/images/galleries/{{ item.image }}" alt="{{ item.title }}">
      <h2>{{ item.title }}</h2>
    </a>
  </li>
{% endfor %}
</ul>
