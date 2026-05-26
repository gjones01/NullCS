import { useEffect, useState } from "react";

type HudNode = {
  id: string;
  x: number;
  y: number;
  value: number;
  drift: number;
};

export function CryoScene({ reducedMotion }: { reducedMotion: boolean }) {
  const [nodes, setNodes] = useState<HudNode[]>(() =>
    Array.from({ length: 10 }, (_, index) => ({
      id: `hud-${index}`,
      x: 12 + index * 8,
      y: 16 + ((index * 11) % 58),
      value: 18 + index * 5,
      drift: index % 2 === 0 ? 1 : -1,
    }))
  );

  useEffect(() => {
    const timer = window.setInterval(() => {
      setNodes((current) =>
        current.map((node, index) => ({
          ...node,
          value: 10 + ((node.value + 2 + index * 3) % 89),
          x: Math.max(8, Math.min(92, node.x + node.drift * 0.7)),
          y: Math.max(10, Math.min(84, node.y + Math.sin((node.value + index) * 0.08) * 0.35)),
          drift: node.x >= 91 || node.x <= 9 ? node.drift * -1 : node.drift,
        }))
      );
    }, reducedMotion ? 3200 : 1200);
    return () => window.clearInterval(timer);
  }, [reducedMotion]);

  return (
    <div className="cryo-scene" aria-hidden>
      <div className="cryo-scanlines" />
      <div className="cryo-hud">
        {nodes.map((node, index) => (
          <div
            key={node.id}
            className="cryo-node"
            style={{ left: `${node.x}%`, top: `${node.y}%`, animationDelay: `${index * 0.28}s` }}
          >
            <span className="cryo-node-dot" />
            <span className="cryo-node-line" />
            <span className="cryo-node-value">{String(node.value).padStart(2, "0")}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
