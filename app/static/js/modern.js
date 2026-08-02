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
})();
