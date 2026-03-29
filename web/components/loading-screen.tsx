"use client";

import { useEffect, useState } from "react";

export function LoadingScreen({
  title,
  subtitle,
  steps = [],
}: {
  title: string;
  subtitle: string;
  steps?: string[];
}) {
  const [stepIndex, setStepIndex] = useState(0);

  useEffect(() => {
    if (steps.length <= 1) {
      return;
    }

    const interval = window.setInterval(() => {
      setStepIndex((current) => (current + 1) % steps.length);
    }, 1400);

    return () => window.clearInterval(interval);
  }, [steps]);

  return (
    <div className="loading-screen" role="status" aria-live="polite">
      <div className="loading-screen-card">
        <div className="loading-mark" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
        <p className="loading-eyebrow">Redactinator</p>
        <h2>{title}</h2>
        <p className="loading-subtitle">{subtitle}</p>
        {steps.length > 0 ? <p className="loading-step">{steps[stepIndex]}</p> : null}
        <div className="loading-track" aria-hidden="true">
          <span />
        </div>
      </div>
    </div>
  );
}
