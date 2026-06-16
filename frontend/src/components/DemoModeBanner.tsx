"use client";

import { useEffect, useState } from "react";
import { FlaskConical } from "lucide-react";
import { isDemoMode, subscribeDemoMode } from "@/lib/demoMode";

/**
 * Visible "Demo mode" indicator. Renders nothing while the live API is
 * answering; once any request falls back to bundled mock data the global flag
 * flips and this banner appears.
 */
export default function DemoModeBanner() {
  const [active, setActive] = useState(false);

  useEffect(() => {
    setActive(isDemoMode());
    return subscribeDemoMode(setActive);
  }, []);

  if (!active) return null;

  return (
    <div
      data-testid="demo-mode-banner"
      className="flex items-center justify-center gap-2 bg-amber-100 px-4 py-2 text-center text-xs font-medium text-amber-800"
    >
      <FlaskConical className="h-3.5 w-3.5" />
      <span>
        Demo mode — backend unreachable, showing bundled sample data. Start the
        API to use live data.
      </span>
    </div>
  );
}
