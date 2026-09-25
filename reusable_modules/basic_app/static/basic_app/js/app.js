// basic_app - small, unobtrusive, domain-generic enhancements. No external dependencies.
// Adapted from RMS's app/static/js/modern.js, keeping only the parts with no dependency
// on any RMS-specific page (mobile nav toggle, flash dismissal, dirty-form tracking).
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

  // Grey out a form's own Save/submit button until something in that form actually
  // changes, and warn (native browser dialog) before leaving the page with any form still
  // dirty. Forms made only of hidden fields (delete/action-only forms, e.g. via a
  // button's form="..." attribute) are left untouched - only a form with at least one
  // visible, editable field is tracked.
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
      return parts.join("");
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
})();
