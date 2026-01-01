---
layout: default
title: Cal Athletics
---

# Cal Athletics

<ul class="gallery-grid">
{% for item in site.data.cal_athletics_galleries %}
  <li>
    <a href="{{ item.url | relative_url }}">
      <img src="{{ '/assets/images/galleries/' | append: item.image | relative_url }}" alt="{{ item.title }}">
      <h2>{{ item.title }}</h2>
    </a>
  </li>
{% endfor %}
</ul>
