"use client";

import { useEffect, useRef } from "react";

/* A rotating particle sphere that stands in for the agent's local knowledge
   graph: points scattered on a sphere (entities), faint links between the
   near ones (relations), a handful of brighter anchor nodes. Pure 2D canvas,
   no dependencies. Pauses off-screen and honours reduced-motion. */

const NODE_COUNT = 82;
const ENTITY_COUNT = 7;
const EDGE_MAX_ANGLE = 0.56; // radians on the unit sphere
const SPIN = 0.0014; // radians / frame

type Node = { x: number; y: number; z: number; entity: boolean };

function fibonacciSphere(n: number): Node[] {
  const pts: Node[] = [];
  const golden = Math.PI * (3 - Math.sqrt(5));
  for (let i = 0; i < n; i++) {
    const y = 1 - (i / (n - 1)) * 2;
    const r = Math.sqrt(Math.max(0, 1 - y * y));
    const theta = golden * i;
    pts.push({ x: Math.cos(theta) * r, y, z: Math.sin(theta) * r, entity: false });
  }
  for (let k = 0; k < ENTITY_COUNT; k++) {
    const idx = Math.floor(((k + 0.5) / ENTITY_COUNT) * n);
    if (pts[idx]) pts[idx].entity = true;
  }
  return pts;
}

export function KnowledgeGraphOrb() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;

    const reduce =
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const base = fibonacciSphere(NODE_COUNT);
    const edges: Array<[number, number]> = [];
    for (let i = 0; i < base.length; i++) {
      for (let j = i + 1; j < base.length; j++) {
        const dot =
          base[i].x * base[j].x + base[i].y * base[j].y + base[i].z * base[j].z;
        if (Math.acos(Math.min(1, Math.max(-1, dot))) < EDGE_MAX_ANGLE) {
          edges.push([i, j]);
        }
      }
    }

    let w = 0;
    let h = 0;
    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      w = rect.width;
      h = rect.height;
      canvas.width = Math.round(w * dpr);
      canvas.height = Math.round(h * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(canvas);

    let running = true;
    const io = new IntersectionObserver(([e]) => (running = e.isIntersecting), {
      threshold: 0,
    });
    io.observe(canvas);

    const tilt = 0.42;
    const ct = Math.cos(tilt);
    const st = Math.sin(tilt);
    let angle = 0;

    const draw = () => {
      const cx = w / 2;
      const cy = h / 2;
      const R = Math.min(w, h) * 0.42;
      const ca = Math.cos(angle);
      const sa = Math.sin(angle);
      ctx.clearRect(0, 0, w, h);

      const proj = base.map((p) => {
        const rx = p.x * ca - p.z * sa;
        const rz = p.x * sa + p.z * ca;
        const y2 = p.y * ct - rz * st;
        const z2 = p.y * st + rz * ct;
        return {
          X: cx + rx * R,
          Y: cy + y2 * R,
          d: (z2 + 1) / 2, // 0 = far, 1 = near
          entity: p.entity,
        };
      });

      for (const [i, j] of edges) {
        const a = proj[i];
        const b = proj[j];
        const d = (a.d + b.d) / 2;
        ctx.strokeStyle = `rgba(201, 199, 187, ${0.03 + d * 0.13})`;
        ctx.lineWidth = 0.5 + d * 0.5;
        ctx.beginPath();
        ctx.moveTo(a.X, a.Y);
        ctx.lineTo(b.X, b.Y);
        ctx.stroke();
      }

      const order = proj.map((_, i) => i).sort((p, q) => proj[p].d - proj[q].d);
      for (const i of order) {
        const p = proj[i];
        ctx.beginPath();
        if (p.entity) {
          ctx.fillStyle = `rgba(246, 221, 226, ${0.28 + p.d * 0.6})`;
          ctx.shadowColor = "rgba(246, 221, 226, 0.55)";
          ctx.shadowBlur = 9 * p.d;
          ctx.arc(p.X, p.Y, 1.7 + p.d * 3.3, 0, Math.PI * 2);
          ctx.fill();
          ctx.shadowBlur = 0;
        } else {
          ctx.fillStyle = `rgba(226, 227, 214, ${0.12 + p.d * 0.5})`;
          ctx.arc(p.X, p.Y, 0.7 + p.d * 1.7, 0, Math.PI * 2);
          ctx.fill();
        }
      }
    };

    let raf = 0;
    const tick = () => {
      if (running) {
        angle += SPIN;
        draw();
      }
      raf = requestAnimationFrame(tick);
    };

    if (reduce) {
      draw();
    } else {
      raf = requestAnimationFrame(tick);
    }

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      io.disconnect();
    };
  }, []);

  return <canvas ref={canvasRef} className="kgraph__canvas" aria-hidden="true" />;
}
