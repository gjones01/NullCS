import { useEffect, useRef } from 'react';

export function DesktopAtmosphere({ paused }: { paused: boolean }) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = ref.current, ctx = canvas?.getContext('2d');
    if (!canvas || !ctx) return;
    const surface = canvas, context = ctx;
    const reduced = matchMedia('(prefers-reduced-motion: reduce)');
    let frame = 0, previous = 0, phase = 0, width = 0, height = 0;
    const pointer = { x: 0, y: 0 };
    function draw(dt: number) {
      phase += dt * 0.00008;
      context.clearRect(0, 0, width, height);
      context.save(); context.translate(width * 0.73 + pointer.x * 12, height * 0.37 + pointer.y * 10);
      for (let i = 0; i < 28; i++) {
        const angle = i * 0.11 + phase;
        context.strokeStyle = `rgba(107,187,255,${0.025 + (i % 5) * 0.007})`;
        context.lineWidth = 0.8;
        context.beginPath(); context.ellipse(0, 0, 180 + i * 3, 90 + i * 6, angle, 0, Math.PI * 2); context.stroke();
      }
      for (let i = 0; i < 36; i++) {
        const angle = i * 2.399 + phase * 0.3, radius = 130 + i * 9;
        context.fillStyle = `rgba(160,215,255,${0.12 + (i % 4) * 0.09})`;
        context.beginPath(); context.arc(Math.cos(angle) * radius, Math.sin(angle) * radius * 0.7, 1, 0, Math.PI * 2); context.fill();
      }
      context.restore();
    }
    function tick(now: number) { if (now - previous > 33.3) { draw(Math.min(50, now - previous)); previous = now; } frame = requestAnimationFrame(tick); }
    function sync() { cancelAnimationFrame(frame); if (!paused && !reduced.matches && !document.hidden) { previous = performance.now(); frame = requestAnimationFrame(tick); } else draw(0); }
    function resize() { width = innerWidth; height = innerHeight; const dpr = Math.min(devicePixelRatio, 1.5); surface.width = width * dpr; surface.height = height * dpr; context.setTransform(dpr, 0, 0, dpr, 0, 0); draw(0); }
    function move(event: PointerEvent) { pointer.x = event.clientX / width - 0.5; pointer.y = event.clientY / height - 0.5; }
    resize(); sync(); window.addEventListener('resize', resize); window.addEventListener('pointermove', move, { passive: true }); document.addEventListener('visibilitychange', sync); reduced.addEventListener('change', sync);
    return () => { cancelAnimationFrame(frame); window.removeEventListener('resize', resize); window.removeEventListener('pointermove', move); document.removeEventListener('visibilitychange', sync); reduced.removeEventListener('change', sync); };
  }, [paused]);
  return <canvas className="desktop-atmosphere" ref={ref} aria-hidden="true" />;
}
