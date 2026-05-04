import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useMemo, useState } from "react";

type ProcessingOverlayProps = {
  title: string;
  subtitle: string;
  steps: string[];
  activeStep: number;
  logs: string;
  reducedMotion: boolean;
};

const loadingFacts = [
  "Counter-Strike started in 1999 as a Half-Life mod before becoming its own genre-defining game.",
  "Through 1.6, Source, Global Offensive, and CS2, Counter-Strike has basically been the benchmark game for raw FPS fundamentals.",
  "Smokes in CS2 are now dynamic volumetric objects, which is why gunfire and grenades can temporarily carve vision through them.",
  "Valve specifically highlighted that CS:GO hitboxes were made tighter and more model-accurate than Source’s.",
  "Mirage, Inferno, Nuke, and Dust are not just famous maps. They are basically pieces of FPS history at this point.",
  "Wingman is not just small CS. It has its own rank system separate from standard competitive.",
  "Flying Scoutsman intentionally removes the normal movement penalty for shooting while moving, which is why it feels so cursed.",
  "In Arms Race, the final winning weapon is the golden knife, which is one of the most Counter-Strike things ever.",
  "A lot of modern CS map identity comes from readability. Valve has openly discussed making player silhouettes easier to see against map backgrounds.",
  "s1mple has 21 HLTV MVP medals, which is one of the reasons he is so often placed in the GOAT conversation.",
  "dupreeh won five CS:GO Majors and attended all 19 CS:GO-era Majors. That run is absurd.",
  "device has four Major titles and is tied for the most Major playoff appearances.",
  "karrigan became famous not just for trophies, but for staying elite deep into an age range where most pros had already fallen off.",
  "The old Polish Golden Five lineup became legendary long before CS2, winning multiple world titles in the 1.6 era.",
  "Fnatic were the first team to win a Major on home soil at DreamHack Winter 2013 in Sweden.",
  "olofmeister’s infamous Overpass boost at DreamHack Winter 2014 was so notorious that boostmeister became part of his identity.",
  "coldzera’s jumping AWP double on Mirage was immortalized with an in-game graffiti by Valve.",
  "Dosia is still associated with one of the funniest stat lines ever: multiple knife kills in a single series.",
  "XANTARES peek became a community term because his entry style looked outrageously explosive even by pro standards.",
  "The MongolZ became one of the biggest breakthrough stories in modern CS by pushing Mongolia into the global elite conversation.",
  "YEKINDAR once joked that bLitz was a chess grandmaster because of how cerebral his calling felt.",
  "The MongolZ once clinched a Major playoff spot over G2 in a Dust2 game that needed five overtimes.",
  "HLTV’s Top 20 list has been running since 2010, which is why those rankings matter so much in CS culture.",
  "HLTV MVP awards are not just popularity trophies. They are tied to standout performance at specific events.",
  "A huge part of pro CS is economy management. Winning the round is only half the game; surviving with rifles matters too.",
  "Counter-strafing became iconic in CS because stopping cleanly before the shot is one of the core skills that separates casual aim from CS aim.",
  "Great CS players are often remembered as much for timing and spacing as for mechanical aim.",
  "The best lurkers in CS are not just flankers. They are information thieves who weaponize silence.",
  "Nuke has always been one of the weirdest iconic maps because verticality matters there more than on almost any other classic map.",
  "Dust2 is so deeply embedded in FPS culture that even people who do not play CS usually recognize Long, Mid, and B tunnels.",
  "Inferno’s identity has always been utility-heavy. If you hate nades, that map hates you back.",
  "Mirage became a default benchmark map partly because it tests nearly every classic CS skill: spacing, utility, mid control, trading, and clutching.",
  "In CS, some players are remembered for one role forever: the AWPer, the IGL, the closer, the anchor, the entry.",
  "The observer experience became important early. Valve was already talking about spectator UI improvements back in 2012.",
  "Community-made maps have always mattered in Counter-Strike; Valve launched the Maps Workshop in CS:GO specifically to make that pipeline easier.",
  "A lot of CS history came from LANs, which is why offline trophies still carry a different kind of aura than online runs.",
  "Cheat discussions exist in every era of CS, which is one reason demo review culture became so obsessive.",
  "The hardest suspicious cases are not the rage hackers. They are the players who look almost normal.",
  "Counter-Strike has survived for decades because the core loop is timeless: information, nerves, mechanics, economy, and one shot changing everything.",
];

function initialFactIndex() {
  return Math.floor(Math.random() * loadingFacts.length);
}

export function ProcessingOverlay({ title, subtitle, steps, activeStep, logs, reducedMotion }: ProcessingOverlayProps) {
  const [factIndex, setFactIndex] = useState(initialFactIndex);
  const [factVisible, setFactVisible] = useState(true);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [showDetails, setShowDetails] = useState(false);

  useEffect(() => {
    if (reducedMotion) return;
    const swapMs = 18000;
    const fadeMs = 900;
    const timer = window.setInterval(() => {
      setFactVisible(false);
      window.setTimeout(() => {
        setFactIndex((current) => (current + 1 + Math.floor(Math.random() * 5)) % loadingFacts.length);
        setFactVisible(true);
      }, fadeMs);
    }, swapMs);
    return () => window.clearInterval(timer);
  }, [reducedMotion]);

  useEffect(() => {
    const startedAt = Date.now();
    const timer = window.setInterval(() => {
      setElapsedSeconds(Math.floor((Date.now() - startedAt) / 1000));
    }, 1000);
    return () => window.clearInterval(timer);
  }, []);

  const activeLabel = useMemo(() => steps[Math.max(0, Math.min(activeStep, steps.length - 1))] || subtitle, [activeStep, steps, subtitle]);

  return (
    <div className="processing-shell">
      <div className="processing-bg-stack" aria-hidden>
        <div className="processing-bg processing-bg-base" />
        <div className="processing-bg processing-bg-image" />
        <div className="processing-bg processing-bg-vignette" />
      </div>
      <div className="processing-grid">
        <motion.div
          className="processing-card"
          initial={{ opacity: 0, y: 20, filter: "blur(8px)" }}
          animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
          transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
        >
          <div className="processing-head">
            <span className="eyebrow">Live analysis</span>
            <h2>{title}</h2>
            <p>{activeLabel}</p>
          </div>

          <div className="processing-steps">
            {steps.map((step, idx) => {
              const done = idx < activeStep;
              const current = idx === activeStep;
              return (
                <div key={step} className={current ? "processing-step active" : done ? "processing-step done" : "processing-step"}>
                  <div className="processing-step-left">
                    <span className="processing-step-dot" />
                    <span>{step}</span>
                  </div>
                  <span className="processing-step-state">{done ? "done" : current ? "active" : "queued"}</span>
                </div>
              );
            })}
          </div>

          <div className="processing-pulse-row" aria-hidden>
            {[0, 1, 2, 3].map((i) => (
              <motion.div
                key={i}
                className="processing-pulse"
                animate={reducedMotion ? { opacity: 0.55 } : { opacity: [0.24, 1, 0.24], scaleX: [0.9, 1, 0.9] }}
                transition={{ duration: 1.2, delay: i * 0.16, repeat: Infinity, ease: "easeInOut" }}
              />
            ))}
          </div>

          <div className="processing-fact-card">
            <div className="processing-fact-meta">
              <span className="eyebrow">CS fact while you wait</span>
              <span className="processing-fact-timer">{reducedMotion ? "static" : "rotates every ~18s"}</span>
            </div>
            <AnimatePresence mode="wait">
              {factVisible ? (
                <motion.p
                  key={factIndex}
                  className="processing-fact-text"
                  initial={{ opacity: 0, y: 14, filter: "blur(6px)" }}
                  animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
                  exit={{ opacity: 0, y: -10, filter: "blur(6px)" }}
                  transition={{ duration: reducedMotion ? 0 : 0.65, ease: [0.22, 1, 0.36, 1] }}
                >
                  {loadingFacts[factIndex]}
                </motion.p>
              ) : null}
            </AnimatePresence>
          </div>

          <div className="processing-debug-card">
            <div>
              <span className="eyebrow">Runtime note</span>
              <p>
                Elapsed {Math.floor(elapsedSeconds / 60)}:{String(elapsedSeconds % 60).padStart(2, "0")}. Large demos,
                first-run Windows scanning, or slow disks can make parsing take several minutes.
              </p>
            </div>
            {logs?.trim() ? (
              <button className="processing-debug-toggle" type="button" onClick={() => setShowDetails((value) => !value)}>
                {showDetails ? "Hide logs" : "Show logs"}
              </button>
            ) : null}
          </div>

          {showDetails && logs?.trim() ? (
            <pre className="processing-log-output">{logs.trim().slice(-3000)}</pre>
          ) : null}
        </motion.div>
      </div>
    </div>
  );
}
