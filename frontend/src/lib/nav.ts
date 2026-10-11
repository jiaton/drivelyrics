import { useSyncExternalStore } from "react";

/**
 * Client-side navigation without a router: the app is a handful of screens picked by
 * path in App.tsx. navigate() pushes history (so the browser's back works) and fires
 * popstate, which every useLocation() listens to.
 */
const subscribe = (onChange: () => void) => {
  window.addEventListener("popstate", onChange);
  return () => window.removeEventListener("popstate", onChange);
};

export function useLocation(): string {
  return useSyncExternalStore(subscribe, () => window.location.pathname + window.location.search);
}

export function navigate(to: string, { replace = false } = {}) {
  if (replace) window.history.replaceState(null, "", to);
  else window.history.pushState(null, "", to);
  window.dispatchEvent(new PopStateEvent("popstate"));
}
