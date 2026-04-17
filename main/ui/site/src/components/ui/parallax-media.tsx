"use client";

import { motion, useScroll, useTransform } from "framer-motion";

export function ParallaxMedia({ children }: { children: React.ReactNode }) {
  const { scrollYProgress } = useScroll();
  const y = useTransform(scrollYProgress, [0, 1], [0, -80]);

  return <motion.div className="relative h-full w-full" style={{ y }}>{children}</motion.div>;
}
