---
layout: default
title: UC Berkeley Artwork
galleries_data: uc_berkeley_galleries
---

# Artwork of UC Berkeley

<ul class="gallery-grid">
{% for item in site.data.uc_berkeley_galleries %}
  <li>
    <a href="{{ item.url | relative_url }}">
      <img src="{{ item.image | relative_url }}" alt="{{ item.title }}">
      <h2>{{ item.title }}</h2>
    </a>
  </li>
{% endfor %}
</ul>
