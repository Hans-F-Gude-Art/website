---
layout: default
title: HFGudeArt | Hans F. Gude Fine Art & Illustration
description: "Fine art and illustration. Official Cal (UC Berkeley) Licensed Artist, authorized to affix the University's logos to his images of the UC Berkeley campus and Cal Athletics. Subjects include landscapes, still lifes, portraits, figures, athletics. Preferred mediums include oil paint, pen & ink, gouache, watercolor, charc"
keywords: "gudeart, Gude Art, Hans Gude, Hans F. Gude, Hans Gude Art"
---

<ul class="gallery-grid">
{% for item in site.data.homepage_galleries %}
  <li>
    <a href="{{ item.url | relative_url }}">
      <img src="{{ item.image | relative_url }}" alt="{{ item.title }}">
      <h2>{{ item.title }}</h2>
    </a>
  </li>
{% endfor %}
</ul>
