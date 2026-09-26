// All client JS for the home page, bundled into one hashed file.
import "cavimg"; // registers <cav-img>

// On a Mac, the main Download buttons fetch the Apple Silicon installer (Intel is listed in #download).
// iPads also report "MacIntel", so rule out touch screens.
if (navigator.platform.startsWith("Mac") && navigator.maxTouchPoints < 2) {
  for (const a of document.querySelectorAll<HTMLAnchorElement>("a[data-mac-href]")) {
    a.href = a.dataset.macHref!;
    const label = a.querySelector(".os-label");
    if (label && a.dataset.macLabel) label.textContent = a.dataset.macLabel;
    if (a.dataset.macAria) a.setAttribute("aria-label", a.dataset.macAria);
  }
}

for (const btn of document.querySelectorAll<HTMLButtonElement>(".copy-btn")) {
  const label = btn.querySelector(".copy-label");
  const idle = btn.querySelector(".copy-idle");
  const done = btn.querySelector(".copy-done");
  const status = btn.parentElement?.querySelector(".copy-status");
  let timer: ReturnType<typeof setTimeout> | undefined;
  const set = (text: string, copied: boolean) => {
    if (label) label.textContent = text;
    idle?.classList.toggle("hidden", copied);
    done?.classList.toggle("hidden", !copied);
  };
  btn.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(btn.dataset.copy ?? "");
      set("Copied", true);
      if (status) status.textContent = "Commands copied to the clipboard.";
      clearTimeout(timer);
      timer = setTimeout(() => {
        set("Copy", false);
        if (status) status.textContent = "";
      }, 2000);
    } catch {
      set("Select and press Ctrl+C", false);
    }
  });
}
