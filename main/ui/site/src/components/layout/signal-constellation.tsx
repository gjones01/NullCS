"use client";

import { useEffect, useRef, useState } from "react";
import { Pause, Play } from "lucide-react";

type Particle = { x: number; y: number; z: number; vx: number; vy: number };

export function SignalConstellation() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [paused, setPaused] = useState(false);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d", { alpha: true });
    if (!canvas || !ctx) return;
    const surface = canvas;
    const context = ctx;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
    const coarse = window.matchMedia("(pointer: coarse)");
    let width = 0, height = 0, frame = 0, last = 0, phase = 0;
    let scroll = window.scrollY;
    let particles: Particle[] = [];
    const pointer = { x: -1000, y: -1000 };
    const spacing = 145;

    function resize() {
      width = window.innerWidth;
      height = window.innerHeight;
      const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
      surface.width = Math.round(width * dpr);
      surface.height = Math.round(height * dpr);
      context.setTransform(dpr, 0, 0, dpr, 0, 0);
      const count = Math.min(coarse.matches ? 32 : 85, Math.floor(width * height / 15000));
      particles = Array.from({ length: count }, () => ({
        x: Math.random() * width, y: Math.random() * height,
        z: 0.3 + Math.random() * 0.7,
        vx: (Math.random() - 0.5) * 0.22, vy: (Math.random() - 0.5) * 0.18,
      }));
      draw(0);
    }

    function draw(dt: number) {
      context.clearRect(0, 0, width, height);
      phase += dt * 0.00007;
      const moving = !paused && !reduced.matches;
      const points = particles.map(p => {
        if (moving) {
          p.x = (p.x + p.vx * dt / 16.7 + width) % width;
          p.y = (p.y + p.vy * dt / 16.7 + height) % height;
        }
        let x = p.x;
        const y = ((p.y - (moving ? scroll * p.z * 0.065 : 0)) % height + height) % height;
        const dx = x - pointer.x, dy = y - pointer.y;
        const distance = Math.hypot(dx, dy);
        if (moving && distance < 170 && distance > 0) x += dx / distance * (170 - distance) * 0.12;
        return { x, y, z: p.z };
      });
      // Spatial buckets keep connection checks local instead of all-pairs.
      const buckets = new Map<string, number[]>();
      points.forEach((p, i) => {
        const key = `${Math.floor(p.x / spacing)},${Math.floor(p.y / spacing)}`;
        const bucket = buckets.get(key) || [];
        bucket.push(i); buckets.set(key, bucket);
      });
      points.forEach((p, i) => {
        const cx = Math.floor(p.x / spacing), cy = Math.floor(p.y / spacing);
        for (let dx = -1; dx <= 1; dx++) for (let dy = -1; dy <= 1; dy++) {
          for (const j of buckets.get(`${cx + dx},${cy + dy}`) || []) {
            if (j <= i) continue;
            const q = points[j], distance = Math.hypot(p.x - q.x, p.y - q.y);
            if (distance >= spacing) continue;
            context.strokeStyle = `rgba(78,166,255,${(1 - distance / spacing) * 0.22})`;
            context.lineWidth = 0.6;
            context.beginPath(); context.moveTo(p.x, p.y); context.lineTo(q.x, q.y); context.stroke();
          }
        }
        context.fillStyle = `rgba(139,205,255,${0.25 + p.z * 0.4})`;
        context.beginPath(); context.arc(p.x, p.y, 0.7 + p.z, 0, Math.PI * 2); context.fill();
        if (moving && Math.hypot(p.x - pointer.x, p.y - pointer.y) < 150) {
          context.strokeStyle = "rgba(104,193,255,0.16)";
          context.beginPath(); context.moveTo(p.x, p.y); context.lineTo(pointer.x, pointer.y); context.stroke();
        }
      });
      // Three open orbital traces add depth without filters or additional DOM layers.
      context.save(); context.translate(width * 0.82, height * 0.4);
      for (let i = 0; i < 3; i++) {
        context.strokeStyle = `rgba(103,176,248,${0.055 + i * 0.015})`;
        context.lineWidth = 0.8;
        context.beginPath();
        context.ellipse(0, 0, 170 + i * 65, 240 + i * 55, phase + i * 0.5, 0.3, 4.8);
        context.stroke();
      }
      context.restore();
    }
    function tick(now: number) {
      if (now - last >= 1000 / 30) {
        draw(Math.min(now - last, 50)); last = now;
      }
      frame = requestAnimationFrame(tick);
    }
    function sync() {
      cancelAnimationFrame(frame);
      last = performance.now();
      if (!document.hidden && !paused && !reduced.matches) frame = requestAnimationFrame(tick);
      else draw(0);
    }
    function onPointer(event: PointerEvent) {
      if (event.pointerType === "mouse") { pointer.x = event.clientX; pointer.y = event.clientY; }
    }
    function onLeave() { pointer.x = -1000; pointer.y = -1000; }
    function onScroll() { scroll = window.scrollY; }
    resize(); sync();
    window.addEventListener("resize", resize);
    window.addEventListener("pointermove", onPointer, { passive: true });
    document.addEventListener("pointerleave", onLeave);
    window.addEventListener("scroll", onScroll, { passive: true });
    document.addEventListener("visibilitychange", sync);
    reduced.addEventListener("change", sync);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("resize", resize);
      window.removeEventListener("pointermove", onPointer);
      document.removeEventListener("pointerleave", onLeave);
      window.removeEventListener("scroll", onScroll);
      document.removeEventListener("visibilitychange", sync);
      reduced.removeEventListener("change", sync);
    };
  }, [paused]);

  return <>
    <canvas ref={canvasRef} aria-hidden="true" className="pointer-events-none fixed inset-0 -z-10 h-screen w-full" />
    <button type="button" onClick={() => setPaused(value => !value)} aria-pressed={paused}
      aria-label={paused ? "Resume background animation" : "Pause background animation"}
      className="ambient-toggle fixed bottom-4 right-4 z-50 flex items-center gap-2 rounded-full border border-sky-300/20 bg-[#080e19]/95 px-3 py-2 text-xs text-sky-200 shadow-lg transition-colors hover:border-sky-300/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary">
      {paused ? <Play size={12} /> : <Pause size={12} />}<span className="hidden sm:inline">Background</span>
    </button>
  </>;
}
