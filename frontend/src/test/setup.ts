import "@testing-library/jest-dom/vitest"

// jsdom doesn't implement matchMedia; next-themes (system dark-mode detection) needs it to exist.
if (!window.matchMedia) {
  window.matchMedia = (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  })
}

// jsdom doesn't implement ResizeObserver either; several Radix primitives (Tooltip, Select,
// Popover, ...) measure elements with it. A no-op is fine — layout-dependent assertions aren't
// what these tests check.
if (!window.ResizeObserver) {
  window.ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
}
