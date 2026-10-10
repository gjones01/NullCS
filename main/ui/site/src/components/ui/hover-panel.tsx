"use client";

import { motion, useMotionTemplate, useMotionValue, useReducedMotion, useSpring } from "framer-motion";
import { cn } from "@/lib/utils";

export function HoverPanel({ children, className }: { children: React.ReactNode; className?: string }) {
  const reduced = useReducedMotion();
  const x = useMotionValue(50), y = useMotionValue(50);
  const tiltX = useSpring(0, { stiffness: 160, damping: 24 });
  const tiltY = useSpring(0, { stiffness: 160, damping: 24 });
  const background = useMotionTemplate`radial-gradient(circle at ${x}% ${y}%, rgba(99,184,255,0.13), transparent 65%)`;
  return (
    <motion.div
      onPointerMove={event => {
        if (reduced || event.pointerType !== "mouse") return;
        const bounds = event.currentTarget.getBoundingClientRect();
        const px = (event.clientX - bounds.left) / bounds.width;
        const py = (event.clientY - bounds.top) / bounds.height;
        x.set(px * 100); y.set(py * 100);
        tiltX.set((0.5 - py) * 4); tiltY.set((px - 0.5) * 4);
      }}
      onPointerLeave={() => { tiltX.set(0); tiltY.set(0); }}
      whileHover={reduced ? undefined : { y: -5 }}
      style={{ rotateX: reduced ? 0 : tiltX, rotateY: reduced ? 0 : tiltY, transformPerspective: 900 }}
      transition={{ type: "spring", stiffness: 180, damping: 22 }}
      className={cn("group relative", className)}
    >
      <motion.div aria-hidden="true" style={{ background, borderRadius: "inherit" }} className="pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-300 group-hover:opacity-100" />
      {children}
    </motion.div>
  );
}
