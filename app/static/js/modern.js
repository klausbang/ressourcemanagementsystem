// RMS Modern UI — small, unobtrusive enhancements. No external dependencies.
(function () {
  "use strict";

  // Mobile nav toggle
  var navToggle = document.getElementById("navToggle");
  var mainNav = document.getElementById("mainNav");
  if (navToggle && mainNav) {
    navToggle.addEventListener("click", function () {
      var open = mainNav.classList.toggle("open");
      navToggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }

  // Flash messages: manual close + auto-dismiss
  document.querySelectorAll(".flash").forEach(function (flash) {
    var closeBtn = flash.querySelector(".flash-close");
    if (closeBtn) {
      closeBtn.addEventListener("click", function () {
        flash.remove();
      });
    }
    window.setTimeout(function () {
      if (flash && flash.parentNode) {
        flash.style.transition = "opacity 0.4s ease";
        flash.style.opacity = "0";
        window.setTimeout(function () { flash.remove(); }, 400);
      }
    }, 6000);
  });

  // Confirm before destructive actions
  document.querySelectorAll("button[data-confirm]").forEach(function (btn) {
    btn.addEventListener("click", function (e) {
      if (!window.confirm(btn.getAttribute("data-confirm"))) {
        e.preventDefault();
      }
    });
  });

  // Preserve scroll position across a Save/Add/Apply round trip (a plain POST-redirect-GET,
  // which otherwise always lands the browser back at the top of the page). Keyed by path
  // only (not query string), since most actions redirect back to the same page with a
  // different query (e.g. a different ?tab=), which should still count as "the same page".
  (function () {
    var key = "rms-scroll:" + location.pathname;
    document.addEventListener(
      "submit",
      function (e) {
        var form = e.target;
        if (form && form.tagName === "FORM" && (form.method || "get").toLowerCase() === "post") {
          try {
            sessionStorage.setItem(key, String(window.scrollY));
          } catch (err) { /* sessionStorage unavailable; scroll just won't be restored */ }
        }
      },
      true
    );
    var saved = null;
    try {
      saved = sessionStorage.getItem(key);
      if (saved !== null) sessionStorage.removeItem(key);
    } catch (err) { /* ignore */ }
    if (saved !== null) {
      window.scrollTo(0, parseInt(saved, 10));
    }
  })();

  // Grey out a form's own Save/submit button until something in that form actually
  // changes, and warn (native browser dialog) before leaving the page with any form still
  // dirty. Forms made only of hidden fields (the various delete/move/action-only forms
  // used via a button's form="..." attribute elsewhere on the page) are left untouched -
  // only a form with at least one visible, editable field is tracked.
  (function () {
    var EDITABLE_SELECTOR = "input:not([type=hidden]):not([type=submit]):not([type=button]), select, textarea";
    var dirtyForms = new Set();

    function serialize(form) {
      var parts = [];
      form.querySelectorAll(EDITABLE_SELECTOR).forEach(function (el) {
        if (!el.name) return;
        if (el.type === "checkbox" || el.type === "radio") {
          parts.push(el.name + "=" + el.checked);
        } else {
          parts.push(el.name + "=" + el.value);
        }
      });
      return parts.join("");
    }

    document.querySelectorAll("form").forEach(function (form) {
      if ((form.method || "get").toLowerCase() !== "post") return;
      var editable = form.querySelectorAll(EDITABLE_SELECTOR);
      if (editable.length === 0) return;

      var ownButtons = Array.prototype.filter.call(
        form.querySelectorAll('button[type="submit"], input[type="submit"]'),
        function (btn) { return !btn.hasAttribute("form"); }
      );
      if (ownButtons.length === 0) return;

      var initial = serialize(form);

      function refresh() {
        var isDirty = serialize(form) !== initial;
        if (isDirty) {
          dirtyForms.add(form);
        } else {
          dirtyForms.delete(form);
        }
        ownButtons.forEach(function (btn) { btn.disabled = !isDirty; });
      }

      ownButtons.forEach(function (btn) { btn.disabled = true; });
      form.addEventListener("input", refresh);
      form.addEventListener("change", refresh);
      form.addEventListener("submit", function () { dirtyForms.delete(form); });
    });

    window.addEventListener("beforeunload", function (e) {
      if (dirtyForms.size > 0) {
        e.preventDefault();
        e.returnValue = "";
      }
    });
  })();

  // Make the floating "P" proposal dialog draggable by its title bar, so it can be moved
  // out of the way of whatever part of the page it's covering while writing a proposal
  // about that exact area.
  (function () {
    var dialog = document.getElementById("proposalDialog");
    var handle = document.getElementById("proposalDialogHandle");
    if (!dialog || !handle) return;

    var dragging = false;
    var startX = 0, startY = 0, startLeft = 0, startTop = 0;

    handle.addEventListener("pointerdown", function (e) {
      dragging = true;
      var rect = dialog.getBoundingClientRect();
      // First drag: switch from the browser's centered auto-margin layout to an
      // explicit fixed position matching where it currently is, so it doesn't jump.
      dialog.style.margin = "0";
      dialog.style.position = "fixed";
      dialog.style.left = rect.left + "px";
      dialog.style.top = rect.top + "px";
      startLeft = rect.left;
      startTop = rect.top;
      startX = e.clientX;
      startY = e.clientY;
      handle.setPointerCapture(e.pointerId);
    });

    handle.addEventListener("pointermove", function (e) {
      if (!dragging) return;
      dialog.style.left = startLeft + (e.clientX - startX) + "px";
      dialog.style.top = startTop + (e.clientY - startY) + "px";
    });

    function stopDragging() { dragging = false; }
    handle.addEventListener("pointerup", stopDragging);
    handle.addEventListener("pointercancel", stopDragging);

    // Reset to the browser's default centered position each time the dialog reopens,
    // so a drag on one report doesn't leave it off-screen the next time it's used.
    dialog.addEventListener("close", function () {
      dialog.style.position = "";
      dialog.style.margin = "";
      dialog.style.left = "";
      dialog.style.top = "";
    });
  })();

  // Phase 28-30 (+ follow-up ids 38-40): Visual Schedule tab interactions. A queue card,
  // or an already-placed "planned" chip, can be armed for placement three ways: its own
  // visible link (queue's "Select", or a chip's "Move this test" inside its <details> -
  // both keyboard/no-JS reachable), a double-click on the card/chip as a mouse shortcut
  // to the same link's URL, or a drag straight onto a grid cell (which fills in and
  // submits that cell's own plain placement form - click and keyboard use that same form
  // directly via its "Place here" button). A plain single click on a chip only opens its
  // <details> to show what it is, without arming anything - proposal id 40, so a stray
  // click no longer silently arms a reschedule. Proposal id 39: after any of these round
  // trips, restore keyboard focus to the same ordered test's element (wherever it now
  // renders), instead of the browser resetting focus to the top of the page.
  (function () {
    var panel = document.getElementById("panel-visual");
    if (!panel) return;

    var FOCUS_KEY = "rms-vis-focus:" + location.pathname;

    function stashFocus(id) {
      if (!id) return;
      try { sessionStorage.setItem(FOCUS_KEY, id); } catch (err) { /* sessionStorage unavailable */ }
    }

    var draggedId = null;

    panel.querySelectorAll("[draggable=true][data-ordered-test-id]").forEach(function (el) {
      el.addEventListener("dragstart", function (e) {
        draggedId = el.getAttribute("data-ordered-test-id");
        el.classList.add("dragging");
        if (e.dataTransfer) {
          e.dataTransfer.setData("text/plain", draggedId || "");
          e.dataTransfer.effectAllowed = "move";
        }
      });
      el.addEventListener("dragend", function () {
        el.classList.remove("dragging");
      });
    });

    panel.querySelectorAll(".vis-day-cell").forEach(function (cell) {
      cell.addEventListener("dragover", function (e) {
        e.preventDefault();
        cell.classList.add("dragover");
      });
      cell.addEventListener("dragleave", function () {
        cell.classList.remove("dragover");
      });
      cell.addEventListener("drop", function (e) {
        e.preventDefault();
        cell.classList.remove("dragover");
        var id = draggedId || (e.dataTransfer && e.dataTransfer.getData("text/plain"));
        if (!id) return;
        var form = cell.querySelector(".vis-cell-form");
        var input = form && form.querySelector(".vis-cell-target-input");
        if (!form || !input) return;
        input.value = id;
        stashFocus(id);
        form.submit();
      });
    });

    panel.querySelectorAll("[data-select-href]").forEach(function (el) {
      el.addEventListener("dblclick", function (e) {
        e.preventDefault();
        stashFocus(el.getAttribute("data-ordered-test-id"));
        location.href = el.getAttribute("data-select-href");
      });
    });

    panel.querySelectorAll("[data-vis-nav]").forEach(function (a) {
      a.addEventListener("click", function () {
        var owner = a.closest("[data-ordered-test-id]");
        stashFocus(owner && owner.getAttribute("data-ordered-test-id"));
      });
    });

    panel.querySelectorAll(".vis-cell-form").forEach(function (form) {
      form.addEventListener("submit", function () {
        var input = form.querySelector(".vis-cell-target-input");
        stashFocus(input && input.value);
      });
    });

    var pendingId = null;
    try {
      pendingId = sessionStorage.getItem(FOCUS_KEY);
      if (pendingId !== null) sessionStorage.removeItem(FOCUS_KEY);
    } catch (err) { /* ignore */ }
    if (pendingId) {
      var target = panel.querySelector('[data-ordered-test-id="' + pendingId + '"]');
      var focusable = target && (target.matches("summary, a, button") ? target : target.querySelector("summary, a, button"));
      (focusable || panel).focus();
    }
  })();
})();
