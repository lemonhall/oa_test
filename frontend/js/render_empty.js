function renderEmpty(listEl, text) {
  listEl.innerHTML = "";
  const empty = document.createElement("div");
  empty.className = "muted";
  empty.textContent = text;
  listEl.appendChild(empty);
}

