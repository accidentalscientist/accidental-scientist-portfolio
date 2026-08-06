function enhanceSettingsButton() {
  const button = document.querySelector(".settings-trigger");
  if (!button || button.classList.contains("nav-icon-button")) return Boolean(button);

  button.classList.add("nav-icon-button");
  button.setAttribute("aria-label", "Settings");
  button.setAttribute("title", "Settings");
  button.innerHTML = '<svg class="nav-symbol" aria-hidden="true"><use href="#icon-settings"></use></svg><span class="visually-hidden">Settings</span>';
  return true;
}

if (!enhanceSettingsButton()) {
  const observer = new MutationObserver(() => {
    if (enhanceSettingsButton()) observer.disconnect();
  });
  observer.observe(document.body, { childList: true, subtree: true });
}

function loadArtwork(url) {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.addEventListener("load", () => resolve({ width: image.naturalWidth, height: image.naturalHeight }));
    image.addEventListener("error", reject);
    image.src = url;
  });
}

function alignPanelArtwork(selectors, dimensions, positioning = {}) {
  const panels = selectors.map((selector) => document.querySelector(selector)).filter(Boolean);
  if (!panels.length) return;

  const rects = panels.map((panel) => panel.getBoundingClientRect());
  const group = {
    left: Math.min(...rects.map((rect) => rect.left)),
    top: Math.min(...rects.map((rect) => rect.top)),
    right: Math.max(...rects.map((rect) => rect.right)),
    bottom: Math.max(...rects.map((rect) => rect.bottom)),
  };
  const groupWidth = group.right - group.left;
  const groupHeight = group.bottom - group.top;
  const scale = Math.max(groupWidth / dimensions.width, groupHeight / dimensions.height) * (positioning.zoom || 1);
  const artworkWidth = dimensions.width * scale;
  const artworkHeight = dimensions.height * scale;
  const artworkLeft = group.left + (groupWidth - artworkWidth) / 2 + groupWidth * (positioning.x || 0);
  const artworkTop = group.top + (groupHeight - artworkHeight) / 2 + groupHeight * (positioning.y || 0);

  panels.forEach((panel, index) => {
    const rect = rects[index];
    panel.style.backgroundSize = `100% 100%, ${artworkWidth}px ${artworkHeight}px`;
    panel.style.backgroundPosition = `center, ${artworkLeft - rect.left}px ${artworkTop - rect.top}px`;
  });
}

const artworkGroups = [
  {
    selectors: [".execution-focus-strip", ".daily-panel", ".ledger-panel"],
    url: "/static/life_compass/assets/sail-hero.png",
    positioning: { zoom: 1.05, x: -0.02, y: -0.03 },
  },
  {
    selectors: [".calendar-panel", ".kanban-panel"],
    url: "/static/life_compass/assets/roman-bireme-explorer.webp",
    positioning: { zoom: 1.35, x: -0.08, y: -0.18 },
  },
];

Promise.all(artworkGroups.map(async (group) => ({ ...group, dimensions: await loadArtwork(group.url) })))
  .then((loadedGroups) => {
    let alignmentFrame;
    const alignAllArtwork = () => {
      window.cancelAnimationFrame(alignmentFrame);
      alignmentFrame = window.requestAnimationFrame(() => {
        loadedGroups.forEach((group) => alignPanelArtwork(group.selectors, group.dimensions, group.positioning));
      });
    };
    const resizeObserver = new ResizeObserver(alignAllArtwork);
    loadedGroups.flatMap((group) => group.selectors).forEach((selector) => {
      const panel = document.querySelector(selector);
      if (panel) resizeObserver.observe(panel);
    });
    window.addEventListener("resize", alignAllArtwork);
    alignAllArtwork();
  })
  .catch(() => {
    // The CSS cover treatment remains as a safe fallback if an image fails.
  });
