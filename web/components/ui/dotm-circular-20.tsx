"use client";

import type { CSSProperties } from "react";

interface DotmCircular20Props {
  /** Outer diameter of the ring, in px. */
  size?: number;
  /** Diameter of each dot, in px. */
  dotSize?: number;
  /** Seconds for one full revolution of the trail. */
  duration?: number;
  /** Dot colour. Defaults to the current text colour. */
  color?: string;
  className?: string;
}

const COUNT = 20;

/**
 * Twenty dots evenly spaced on a circle, with a brightness trail that sweeps
 * around the ring — a minimal indeterminate loader. Each dot runs the same
 * fade keyframe, offset by a fraction of the duration so the peak walks the
 * circle. Honours prefers-reduced-motion.
 */
export function DotmCircular20({
  size = 40,
  dotSize = 4,
  duration = 1.6,
  color = "currentColor",
  className,
}: DotmCircular20Props) {
  const radius = (size - dotSize) / 2;

  return (
    <div
      className={`dotm20${className ? ` ${className}` : ""}`}
      style={{ width: size, height: size }}
      role="status"
      aria-label="Loading"
    >
      {Array.from({ length: COUNT }).map((_, i) => {
        const angle = (i / COUNT) * 2 * Math.PI;
        return (
          <span
            key={i}
            className="dotm20__dot"
            style={
              {
                width: dotSize,
                height: dotSize,
                left: size / 2 + radius * Math.cos(angle),
                top: size / 2 + radius * Math.sin(angle),
                background: color,
                animationDuration: `${duration}s`,
                animationDelay: `${(-duration * i) / COUNT}s`,
              } as CSSProperties
            }
          />
        );
      })}

      <style jsx>{`
        .dotm20 {
          position: relative;
          display: inline-block;
          flex: none;
        }
        .dotm20__dot {
          position: absolute;
          border-radius: 50%;
          transform: translate(-50%, -50%);
          opacity: 0.16;
          animation-name: dotm20-fade;
          animation-timing-function: linear;
          animation-iteration-count: infinite;
        }
        @keyframes dotm20-fade {
          0% {
            opacity: 1;
          }
          70%,
          100% {
            opacity: 0.16;
          }
        }
        @media (prefers-reduced-motion: reduce) {
          .dotm20__dot {
            animation: none;
            opacity: 0.4;
          }
        }
      `}</style>
    </div>
  );
}

export default DotmCircular20;
