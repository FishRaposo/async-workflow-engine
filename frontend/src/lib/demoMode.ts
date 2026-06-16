// A tiny global "demo mode" flag. The API client sets it to true whenever a
// live request fails and we fall back to bundled mock data; the app shell
// subscribes so it can show a visible "Demo mode" indicator.

type Listener = (active: boolean) => void;

let active = false;
const listeners = new Set<Listener>();

export function isDemoMode(): boolean {
  return active;
}

export function setDemoMode(value: boolean): void {
  if (active === value) return;
  active = value;
  listeners.forEach((fn) => fn(active));
}

export function subscribeDemoMode(fn: Listener): () => void {
  listeners.add(fn);
  return () => {
    listeners.delete(fn);
  };
}
