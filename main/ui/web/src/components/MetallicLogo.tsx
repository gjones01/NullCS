import { motion } from "framer-motion";

export function MetallicLogo({ reducedMotion }: { reducedMotion: boolean }) {
  return (
    <motion.div
      className="hero-logo-shell"
      initial={{ opacity: 0, y: 26, scale: 0.94, filter: "blur(10px)" }}
      animate={{ opacity: 1, y: 0, scale: 1, filter: "blur(0px)" }}
      transition={{ duration: 0.85, delay: 0.16, ease: [0.22, 1, 0.36, 1] }}
    >
      <div className="hero-logo-paint-frame hero-logo-static-frame" aria-label="NullCS logo">
        <img className="hero-logo-static" src="/nullcs-logo-cropped.png" alt="NullCS" />
        <motion.div
          className="hero-logo-sheen"
          initial={false}
          animate={reducedMotion ? { opacity: 0.2 } : { opacity: [0.12, 0.34, 0.14] }}
          transition={{ duration: 4.8, repeat: Infinity, ease: "easeInOut" }}
        />
      </div>
    </motion.div>
  );
}
