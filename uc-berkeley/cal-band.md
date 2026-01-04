---
layout: default
title: Cal Marching Band
galleries_data: cal_band_galleries
---

# Berkeley Band

This 4-foot x 6-foot (1.3-m x 2.0-m) oil painting of the band, which the artist created as a donation to the Cal Marching Band, is installed in the band room on the UC Berkeley campus. The painting, which contains 15 figures, is titled *The Cal Band Relaxes in North Tunnel Before the Big Game*. Oil on Canvas, 2013.

<ul class="gallery-grid">
{% for item in site.data.cal_band_galleries %}
  <li>
    <a href="{{ item.url | relative_url }}">
      <img src="{{ item.image | relative_url }}" alt="{{ item.title }}">
      <h2>{{ item.title }}</h2>
    </a>
  </li>
{% endfor %}
</ul>
