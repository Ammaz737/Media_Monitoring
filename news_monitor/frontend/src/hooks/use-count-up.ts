"use client";

import { useEffect, useState } from "react";

function easeOutCubic(t: number) {
  return 1 - Math.pow(1 - t, 3);
}

/** Animate number from 0 → target on mount / when target changes */
export function useCountUp(
  target: number,
  duration = 1200,
  decimals = 0,
  enabled = true
): string {
  const [current, setCurrent] = useState(0);

  useEffect(() => {
    if (!enabled) {
      setCurrent(target);
      return;
    }
    if (target === 0) {
      setCurrent(0);
      return;
    }

    const start = performance.now();
    let frame: number;

    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      const val = easeOutCubic(t) * target;
      setCurrent(val);
      if (t < 1) frame = requestAnimationFrame(tick);
    };

    setCurrent(0);
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [target, duration, enabled]);

  return decimals > 0 ? current.toFixed(decimals) : String(Math.round(current));
}
