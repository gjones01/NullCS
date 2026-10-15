import type { CSSProperties } from "react";

/** Editorial network topology, not a visualization of learned activations. */
export function NeuralNetwork() {
  const sizes = [6, 8, 9, 7, 4];
  const nodes = sizes.map((size, layer) => Array.from({ length: size }, (_, n) => ({
    x: 50 + layer * 125,
    y: 150 + (n - (size - 1) / 2) * 26,
  })));
  return <div className="neural-network">
    <svg viewBox="0 0 600 310" role="img" aria-label="Conceptual neural network with connected nodes and moving signals; not actual model activations">
      <defs><radialGradient id="neural-node"><stop stopColor="#f1fff9" /><stop offset="1" stopColor="#83b7ae" /></radialGradient></defs>
      {nodes.slice(0, -1).flatMap((layer, l) => layer.flatMap((a, i) => nodes[l + 1].filter((_, j) => (i + j) % 3 === 0).map((b, j) => (
        <path key={`${l}-${i}-${j}`} className="neural-wire" style={{ "--delay": `${-(i + j) * .3}s` } as CSSProperties}
          d={`M ${a.x} ${a.y} C ${a.x + 45} ${a.y - 35}, ${b.x - 45} ${b.y + 35}, ${b.x} ${b.y}`} />
      ))))}
      {nodes.flatMap((layer, l) => layer.map((n, i) => <g key={`${l}-${i}`} className="neural-node" style={{ "--delay": `${-(i + l) * .45}s` } as CSSProperties}>
        <circle cx={n.x} cy={n.y} r={i % 3 === 0 ? 8 : 5} fill="url(#neural-node)" />
        <circle cx={n.x} cy={n.y} r={i % 3 === 0 ? 14 : 10} fill="none" stroke="#91bfb6" strokeOpacity=".25" />
      </g>))}
      {['INPUT', 'LAYER 1', 'LAYER 2', 'LAYER 3', 'SUMMARY'].map((label, i) => <text key={label} x={50 + i * 125} y="292" textAnchor="middle">{label}</text>)}
    </svg>
    <p>An illustration of a model combining measurements over time.</p>
  </div>;
}
