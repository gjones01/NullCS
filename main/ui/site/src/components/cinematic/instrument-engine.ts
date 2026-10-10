import * as THREE from "three";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";

export type SceneState = {
  progress: number;
  stage: number;
  channel: number;
  motion: boolean;
};
export type SceneOptions = {
  mode: "hero" | "pipeline" | "telemetry";
  samples?: number[][];
  read: () => SceneState;
  ready: (value: boolean) => void;
};

/** Recorded telemetry and supporting analytical geometry. */
export function mountInstrument(host: HTMLElement, options: SceneOptions) {
  const renderer = new THREE.WebGLRenderer({
    antialias: true,
    alpha: true,
    powerPreference: "low-power",
  });
  renderer.setPixelRatio(
    Math.min(devicePixelRatio, innerWidth < 760 ? 1.25 : 1.5),
  );
  renderer.setClearColor(0x000000, 0);
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.25;
  renderer.domElement.setAttribute("aria-hidden", "true");
  host.appendChild(renderer.domElement);
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(34, 1, 0.1, 60);
  camera.position.set(0, 0, 10);
  const pmrem = new THREE.PMREMGenerator(renderer);
  const room = new RoomEnvironment();
  const environment = pmrem.fromScene(room, 0.04);
  scene.environment = environment.texture;
  room.dispose();
  pmrem.dispose();
  const key = new THREE.DirectionalLight(0xf3f0e5, 4);
  key.position.set(-3, 5, 6);
  scene.add(key);
  const rim = new THREE.DirectionalLight(0xabb8c4, 3);
  rim.position.set(4, -1, 3);
  scene.add(rim);
  scene.add(new THREE.AmbientLight(0xffffff, 0.35));
  const metal = new THREE.MeshStandardMaterial({
    color: 0x555a5c,
    metalness: 1,
    roughness: 0.22,
  });
  const dark = new THREE.MeshStandardMaterial({
    color: 0x151718,
    metalness: 0.9,
    roughness: 0.31,
  });
  const rig = new THREE.Group();
  scene.add(rig);
  const instrument = new THREE.Group();
  rig.add(instrument);
  // Analytical layers: the same instrument opens into six processing planes.
  const layers = new THREE.Group();
  rig.add(layers);
  const plates: THREE.Group[] = [];
  for (let i = 0; i < 6; i++) {
    const group = new THREE.Group();
    const plate = new THREE.Mesh(
      new THREE.BoxGeometry(2.7, 1.8, 0.07),
      i % 2 ? dark : metal,
    );
    group.add(plate);
    const edge = new THREE.LineSegments(
      new THREE.EdgesGeometry(plate.geometry),
      new THREE.LineBasicMaterial({
        color: 0xadb2a9,
        transparent: true,
        opacity: 0.4,
      }),
    );
    group.add(edge);
    const lines: number[] = [];
    const segment = (x: number, y: number, x2: number, y2: number) =>
      lines.push(x, y, 0.06, x2, y2, 0.06);
    const rect = (x: number, y: number, w: number, h: number) => {
      segment(x, y, x + w, y);
      segment(x + w, y, x + w, y + h);
      segment(x + w, y + h, x, y + h);
      segment(x, y + h, x, y);
    };
    if (i === 0) {
      rect(-0.5, -0.65, 1, 1.3);
      for (let j = 0; j < 5; j++)
        segment(-0.3, -0.4 + j * 0.18, 0.25, -0.4 + j * 0.18);
    }
    if (i === 1) {
      for (let j = 0; j < 3; j++)
        for (let k = 0; k < 25; k++) {
          const x = k * 0.08 - 1;
          segment(
            x,
            Math.sin(k * 0.8 + j) * 0.13 + (j - 1) * 0.4,
            x + 0.08,
            Math.sin((k + 1) * 0.8 + j) * 0.13 + (j - 1) * 0.4,
          );
        }
    }
    if (i === 2) {
      for (let j = 0; j < 4; j++) {
        rect(-1 + j * 0.52, -0.5, 0.42, 1);
        for (let k = 0; k < 4; k++)
          segment(
            -0.94 + j * 0.52,
            -0.3 + k * 0.2,
            -0.67 + j * 0.52,
            -0.3 + k * 0.2,
          );
      }
    }
    if (i === 3) {
      for (let j = 0; j < 3; j++)
        for (let a = 0; a < 4; a++)
          for (let b = 0; b < 4; b++)
            segment(
              -0.9 + j * 0.6,
              -0.5 + a * 0.33,
              -0.9 + (j + 1) * 0.6,
              -0.5 + b * 0.33,
            );
    }
    if (i === 4) {
      segment(0, 0.65, 0, 0.3);
      segment(-0.7, 0.05, 0, 0.3);
      segment(0.7, 0.05, 0, 0.3);
      segment(-0.7, 0.05, -1, -0.4);
      segment(-0.7, 0.05, -0.4, -0.4);
      segment(0.7, 0.05, 0.4, -0.4);
      segment(0.7, 0.05, 1, -0.4);
    }
    if (i === 5) {
      for (let j = 0; j < 5; j++) rect(-1, 0.5 - j * 0.24, 1.9 - j * 0.25, 0.1);
    }
    const marks = new THREE.LineSegments(
      new THREE.BufferGeometry().setAttribute(
        "position",
        new THREE.Float32BufferAttribute(lines, 3),
      ),
      new THREE.LineBasicMaterial({
        color: 0xc4cda9,
        transparent: true,
        opacity: 0.55,
      }),
    );
    group.add(marks);
    layers.add(group);
    plates.push(group);
  }
  const signals = new THREE.Group();
  rig.add(signals);
  const traces: THREE.Line[] = [];
  (options.samples || []).forEach((values, j) => {
    const max = Math.max(...values, 0.001);
    const points = values.map(
      (v, i) =>
        new THREE.Vector3(
          (i / (values.length - 1)) * 6 - 3,
          (v / max) * 1.8 - 0.6,
          (j - 1) * 1.2,
        ),
    );
    const line = new THREE.Line(
      new THREE.BufferGeometry().setFromPoints(points),
      new THREE.LineBasicMaterial({
        color: j === 0 ? 0xc4cda9 : 0x777e81,
        transparent: true,
        opacity: 0.85,
      }),
    );
    signals.add(line);
    traces.push(line);
    const base = new THREE.Line(
      new THREE.BufferGeometry().setFromPoints([
        new THREE.Vector3(-3, -0.65, (j - 1) * 1.2),
        new THREE.Vector3(3, -0.65, (j - 1) * 1.2),
      ]),
      new THREE.LineBasicMaterial({ color: 0x45494a }),
    );
    signals.add(base);
  });
  const cursor = new THREE.Mesh(
    new THREE.BoxGeometry(0.015, 2.4, 3.1),
    new THREE.MeshBasicMaterial({
      color: 0xd9dfc7,
      transparent: true,
      opacity: 0.16,
    }),
  );
  signals.add(cursor);
  instrument.visible = options.mode === "hero";
  layers.visible = options.mode === "pipeline";
  signals.visible = options.mode === "telemetry";
  const pointer = { x: 0, y: 0 };
  let visible = false,
    disposed = false,
    frame = 0,
    last = 0,
    elapsed = 0,
    slowFrames = 0,
    reducedQuality = false,
    lastStatic = "";
  function move(e: PointerEvent) {
    const rect = host.getBoundingClientRect();
    pointer.x = (e.clientX - rect.left) / rect.width - 0.5;
    pointer.y = (e.clientY - rect.top) / rect.height - 0.5;
  }
  function resize() {
    const w = host.clientWidth,
      h = host.clientHeight;
    if (!w || !h) return;
    renderer.setSize(w, h);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    lastStatic = "";
  }
  const resizer = new ResizeObserver(resize);
  resizer.observe(host);
  resize();
  const observer = new IntersectionObserver(
    ([entry]) => {
      visible = entry.isIntersecting;
    },
    { threshold: 0.01 },
  );
  observer.observe(host);
  function lost(event: Event) {
    event.preventDefault();
    visible = false;
    options.ready(false);
  }
  renderer.domElement.addEventListener("webglcontextlost", lost);
  host.addEventListener("pointermove", move, { passive: true });
  function tick(now: number) {
    if (disposed) return;
    frame = requestAnimationFrame(tick);
    if (!visible || document.hidden || now - last < 33) return;
    const state = options.read();
    const dt = Math.min(now - last, 80);
    last = now;
    const staticKey = `${state.stage}:${state.channel}`;
    if (!state.motion && lastStatic === staticKey) return;
    if (state.motion) elapsed += dt / 1000;
    const p = state.motion ? state.progress : 0;
    const px = state.motion ? pointer.x : 0,
      py = state.motion ? pointer.y : 0;
    const easing = state.motion ? 0.06 : 1;
    rig.rotation.x +=
      ((options.mode === "telemetry" ? 0.35 : 0.18) +
        py * 0.15 -
        rig.rotation.x) *
      easing;
    rig.rotation.y +=
      ((options.mode === "hero"
        ? -0.42
        : options.mode === "pipeline"
          ? -0.65
          : -0.25) +
        px * 0.22 +
        p * 0.35 -
        rig.rotation.y) *
      easing;
    rig.rotation.z =
      options.mode === "hero" ? -0.18 + Math.sin(elapsed * 0.15) * 0.025 : 0;
    if (options.mode === "hero") {
      instrument.rotation.z = 0.14 + p * 0.12;
      instrument.rotation.y = elapsed * 0.12 + p * 0.5;
      instrument.position.z = p * 0.5;
      rig.position.y = Math.sin(elapsed * 0.4) * 0.035;
      camera.position.z = Math.max(8.9, 10 / camera.aspect);
    }
    if (options.mode === "pipeline") {
      plates.forEach((plate, i) => {
        const z = i === state.stage ? 1.9 : (i - 2.5) * 0.52;
        const x = i === state.stage ? -0.45 : 0.35;
        plate.position.z += (z - plate.position.z) * (state.motion ? 0.08 : 1);
        plate.position.x += (x - plate.position.x) * (state.motion ? 0.08 : 1);
        (plate.children[0] as THREE.Mesh).material =
          i === state.stage ? metal : dark;
      });
      rig.rotation.z = -0.16;
      camera.position.z = 9.6;
    }
    if (options.mode === "telemetry") {
      traces.forEach((line, i) => {
        (line.material as THREE.LineBasicMaterial).color.setHex(
          i === state.channel ? 0xd5dfb4 : 0x60686a,
        );
      });
      cursor.position.x = Math.sin(elapsed * 0.28) * 2.9;
      camera.position.z = Math.max(6, 11 / camera.aspect);
    }
    const started = performance.now();
    renderer.render(scene, camera);
    lastStatic = state.motion ? "" : staticKey;
    if (performance.now() - started > 28) slowFrames++;
    if (slowFrames > 30 && !reducedQuality) {
      renderer.setPixelRatio(1);
      resize();
      reducedQuality = true;
    }
    host.dataset.drawCalls = String(renderer.info.render.calls);
    host.dataset.quality = reducedQuality ? "adaptive" : "standard";
    host.dataset.frames = String(renderer.info.render.frame);
  }
  frame = requestAnimationFrame(tick);
  options.ready(true);
  return () => {
    disposed = true;
    cancelAnimationFrame(frame);
    resizer.disconnect();
    observer.disconnect();
    host.removeEventListener("pointermove", move);
    renderer.domElement.removeEventListener("webglcontextlost", lost);
    const geometries = new Set<THREE.BufferGeometry>(),
      materials = new Set<THREE.Material>();
    scene.traverse((obj) => {
      const mesh = obj as THREE.Mesh;
      if (mesh.geometry) geometries.add(mesh.geometry);
      if (mesh.material)
        (Array.isArray(mesh.material)
          ? mesh.material
          : [mesh.material]
        ).forEach((m) => materials.add(m));
    });
    geometries.forEach((g) => g.dispose());
    materials.forEach((m) => m.dispose());
    environment.dispose();
    renderer.dispose();
    renderer.domElement.remove();
  };
}
