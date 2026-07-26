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
})();
