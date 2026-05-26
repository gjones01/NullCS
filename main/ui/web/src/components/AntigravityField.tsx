import type { CSSProperties } from "react";

type Particle = {
  id: string;
  x: number;
  y: number;
  size: number;
  delay: number;
  duration: number;
};

const PARTICLES: Particle[] = Array.from({ length: 26 }, (_, index) => ({
  id: `anti-${index}`,
  x: 8 + ((index * 11) % 84),
  y: 12 + ((index * 17) % 70),
  size: 1 + ((index * 3) % 4) * 0.45,
  delay: index * 0.16,
  duration: 7 + (index % 5) * 1.2,
}));

export function AntigravityField({ reducedMotion }: { reducedMotion: boolean }) {
  return (
    <div className="antigravity-field" aria-hidden>
      <div className="antigravity-core" />
      {PARTICLES.map((particle) => (
        <span
          key={particle.id}
          className="antigravity-particle"
          style={
            {
              left: `${particle.x}%`,
              top: `${particle.y}%`,
              width: `${particle.size * 6}px`,
              height: `${particle.size * 6}px`,
              animationDelay: `${particle.delay}s`,
              animationDuration: reducedMotion ? "0ms" : `${particle.duration}s`,
            } as CSSProperties
          }
        />
      ))}
    </div>
  );
}
