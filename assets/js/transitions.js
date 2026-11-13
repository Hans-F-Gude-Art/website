// Thumbnail-to-artwork morph for cross-document view transitions.
//
// The stylesheet opts every page into view transitions (@view-transition,
// only without reduced motion) and names the artwork page's image
// `artwork`. Here, a gallery thumbnail takes the same name for the length
// of one transition, so the browser morphs it into the artwork image on
// the way in and back on the way out. Names must be unique on a page, so
// only the one thumbnail for the artwork in question is named.
//
// Loaded as a blocking script in <head>, not with defer: `pagereveal`
// fires before the new page's first render, which a deferred script can
// miss.
(() => {
  const NAME = "artwork";
  const isArtwork = (url) => new URL(url, location.href).pathname.startsWith("/artwork/");

  // The grid image whose link points at `url`, if any.
  function thumbnailFor(url) {
    const target = new URL(url, location.href).href;
    for (const link of document.querySelectorAll(".photo-grid a, .gallery-grid a")) {
      if (link.href === target) return link.querySelector("img");
    }
    return null;
  }

  function nameFor(transition, image) {
    image.style.viewTransitionName = NAME;
    transition.finished.finally(() => {
      image.style.viewTransitionName = "";
    });
  }

  // Leaving a gallery for an artwork: name the clicked thumbnail.
  addEventListener("pageswap", (event) => {
    const url = event.activation?.entry?.url;
    if (!event.viewTransition || !url || !isArtwork(url)) return;
    const image = thumbnailFor(url);
    if (image) nameFor(event.viewTransition, image);
  });

  // Arriving at a gallery from an artwork: name its thumbnail, so the
  // artwork image shrinks back into place.
  addEventListener("pagereveal", (event) => {
    const url = window.navigation?.activation?.from?.url;
    if (!event.viewTransition || !url || !isArtwork(url)) return;
    const reveal = () => {
      const image = thumbnailFor(url);
      if (image) nameFor(event.viewTransition, image);
    };
    // pagereveal can fire before the grid is parsed.
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", reveal, { once: true });
    } else {
      reveal();
    }
  });
})();
