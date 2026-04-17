"use client";

import { motion, useScroll, useTransform } from "framer-motion";

const clusters = [
  {
    className: "left-[6%] top-[12%] w-[34rem]",
    nodes: [
      { x: 10, y: 18, label: "57" },
      { x: 22, y: 34, label: "40" },
      { x: 40, y: 48, label: "48" },
      { x: 58, y: 66, label: "20" },
      { x: 78, y: 38, label: "72" },
      { x: 70, y: 82, label: "44" },
    ],
    lines: [
      [0, 1],
      [1, 2],
      [2, 4],
      [1, 3],
      [3, 5],
    ],
  },
  {
    className: "right-[-3%] top-[36%] w-[28rem]",
    nodes: [
      { x: 18, y: 20, label: "31" },
      { x: 34, y: 36, label: "18" },
      { x: 54, y: 28, label: "62" },
      { x: 68, y: 54, label: "27" },
      { x: 44, y: 70, label: "09" },
      { x: 82, y: 34, label: "51" },
    ],
    lines: [
      [0, 1],
      [1, 2],
      [2, 3],
      [3, 4],
      [2, 5],
    ],
  },
] as const;

export function SignalConstellation() {
  const { scrollYProgress } = useScroll();
  const slowY = useTransform(scrollYProgress, [0, 1], ["0%", "-10%"]);
  const fastY = useTransform(scrollYProgress, [0, 1], ["0%", "-16%"]);

  return (
    <div className="pointer-events-none absolute inset-0 -z-10 overflow-hidden">
      <motion.div className="absolute inset-0 opacity-[0.16]" style={{ y: slowY }}>
        {clusters.map((cluster, idx) => (
          <motion.div
            key={idx}
            className={`absolute aspect-square ${cluster.className}`}
            animate={{ rotate: idx === 0 ? 360 : -360 }}
            transition={{ duration: idx === 0 ? 90 : 110, repeat: Infinity, ease: "linear" }}
          >
            <svg viewBox="0 0 100 100" className="h-full w-full overflow-visible">
              {cluster.lines.map(([a, b], lineIdx) => {
                const start = cluster.nodes[a];
                const end = cluster.nodes[b];
                return (
                  <line
                    key={lineIdx}
                    x1={start.x}
                    y1={start.y}
                    x2={end.x}
                    y2={end.y}
                    stroke="rgba(212,224,255,0.35)"
                    strokeWidth="0.18"
                  />
                );
              })}
              {cluster.nodes.map((node) => (
                <g key={`${node.x}-${node.y}`}>
                  <circle cx={node.x} cy={node.y} r="0.9" fill="rgba(154, 227, 255, 0.9)" />
                  <circle cx={node.x} cy={node.y} r="2.6" fill="rgba(154, 227, 255, 0.08)" />
                  <text
                    x={node.x - 3.8}
                    y={node.y - 2.3}
                    fill="rgba(244,247,255,0.75)"
                    fontSize="3"
                    fontFamily="IBM Plex Sans, sans-serif"
                    letterSpacing="0.08em"
                  >
                    {node.label}
                  </text>
                </g>
              ))}
            </svg>
          </motion.div>
        ))}
      </motion.div>

      <motion.div
        className="absolute inset-x-0 top-[8%] h-[40rem] bg-[radial-gradient(circle_at_center,rgba(255,255,255,0.05),transparent_58%)] opacity-40"
        style={{ y: fastY }}
      />
    </div>
  );
}
