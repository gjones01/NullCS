"use client";

import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

export function HoverPanel({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <motion.div
      whileHover={{ y: -8, scale: 1.01 }}
      transition={{ type: "spring", stiffness: 180, damping: 20, mass: 0.8 }}
      className={cn("group", className)}
    >
      {children}
    </motion.div>
  );
}
