// Site navigation submenus (_includes/header.html).
//
// Each submenu is a <ul hidden> right after its trigger <button>. In the
// wide layout it becomes a popover="auto" opened by the button's
// popovertarget; the native popover provides light dismiss, Escape, and
// focus return, and its toggle event keeps aria-expanded in sync. In the
// narrow layout it is an inline disclosure that the button's click handler
// shows and hides.
//
// `popover` is set with setAttribute(), never the `.popover` property: the
// polyfill, loaded only where the browser lacks popover, would miss a
// property set before it loads.
(() => {
  const script = document.currentScript;
  if (!Object.hasOwn(HTMLElement.prototype, "popover")) {
    const polyfill = document.createElement("script");
    polyfill.src = script.dataset.popoverPolyfill;
    document.head.append(polyfill);
  }

  // Matches the stylesheet's narrow breakpoint (max-width: 37.4375em).
  const wideLayout = matchMedia("(min-width: 37.5em)");
  const canHover = matchMedia("(hover: hover)");
  const anchorSupported = CSS.supports("position-area", "block-end");

  const isOpen = (submenu) => submenu.matches(":is(:popover-open, .\\:popover-open)");

  // Without anchor positioning a popover centers in the viewport; place it
  // below its trigger instead, flipping above when it would not fit.
  function placeBelow(trigger, submenu) {
    const anchor = trigger.getBoundingClientRect();
    const size = submenu.getBoundingClientRect();
    let top = anchor.bottom;
    if (top + size.height > innerHeight) top = Math.max(0, anchor.top - size.height);
    const left = Math.min(Math.max(0, anchor.left), Math.max(0, innerWidth - size.width));
    submenu.style.top = `${top}px`;
    submenu.style.left = `${left}px`;
  }

  for (const item of document.querySelectorAll(".navigation-menu .has-dropdown")) {
    const trigger = item.querySelector(".dropdown-trigger");
    const submenu = trigger && document.getElementById(trigger.getAttribute("aria-controls"));
    if (!submenu) continue;
    // True while the submenu is open only because the pointer is over it.
    let previewing = false;

    const applyLayout = () => {
      if (wideLayout.matches) {
        submenu.setAttribute("popover", "auto");
        submenu.hidden = false;
      } else {
        submenu.removeAttribute("popover");
        submenu.hidden = true;
      }
      previewing = false;
      trigger.setAttribute("aria-expanded", "false");
    };
    applyLayout();
    wideLayout.addEventListener("change", applyLayout);

    submenu.addEventListener("toggle", (event) => {
      const open = event.newState === "open";
      trigger.setAttribute("aria-expanded", String(open));
      if (!open) previewing = false;
      if (open && !anchorSupported) placeBelow(trigger, submenu);
    });

    trigger.addEventListener("click", (event) => {
      if (submenu.hasAttribute("popover")) {
        // A click during a hover preview pins the submenu open instead of
        // letting popovertarget toggle it closed.
        if (previewing) {
          previewing = false;
          event.preventDefault();
        }
        return;
      }
      submenu.hidden = !submenu.hidden;
      trigger.setAttribute("aria-expanded", String(!submenu.hidden));
    });

    item.addEventListener("pointerenter", (event) => {
      if (!submenu.hasAttribute("popover") || !canHover.matches) return;
      if (event.pointerType === "touch" || isOpen(submenu)) return;
      submenu.showPopover({ source: trigger });
      previewing = true;
    });

    item.addEventListener("pointerleave", () => {
      if (previewing && isOpen(submenu)) submenu.hidePopover();
      previewing = false;
    });

    // Tabbing out of the item closes its popover.
    item.addEventListener("focusout", (event) => {
      const next = event.relatedTarget;
      if (next && !item.contains(next) && submenu.hasAttribute("popover") && isOpen(submenu)) {
        submenu.hidePopover();
      }
    });
  }
})();
