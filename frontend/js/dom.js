const $ = (sel) => document.querySelector(sel);

function setError(el, msg) {
  el.textContent = msg || "";
}

