"use strict";
for (const button of document.querySelectorAll("[data-status-filter]")) {
  button.addEventListener("click", () => {
    const wanted = button.dataset.statusFilter;
    for (const row of document.querySelectorAll("[data-status]")) {
      row.hidden = wanted !== "all" && row.dataset.status !== wanted;
    }
    for (const peer of document.querySelectorAll("[data-status-filter]")) {
      peer.setAttribute("aria-pressed", String(peer === button));
    }
  });
}
