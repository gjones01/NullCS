import { useEffect, useRef } from "react";
import * as THREE from "three";

export function ImmersiveHeroScene({ reducedMotion }: { reducedMotion: boolean }) {
  const mountRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (reducedMotion) return;
    const mount = mountRef.current;
    if (!mount) return;

    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x05080d, 0.055);

    const { clientWidth, clientHeight } = mount;
    const camera = new THREE.PerspectiveCamera(38, clientWidth / Math.max(clientHeight, 1), 0.1, 100);
    camera.position.set(0, 0.8, 16);

    const renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true,
      powerPreference: "low-power",
    });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.6));
    renderer.setSize(clientWidth, clientHeight);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    mount.appendChild(renderer.domElement);

    const ambient = new THREE.AmbientLight(0xdfe7ff, 0.82);
    const rim = new THREE.PointLight(0xcde4ff, 10, 36, 2);
    rim.position.set(6, 4, 10);
    const under = new THREE.PointLight(0x7f95ff, 8, 32, 2);
    under.position.set(0, -6, 4);
    scene.add(ambient, rim, under);

    const core = new THREE.Group();
    scene.add(core);

    const glassMaterial = new THREE.MeshPhysicalMaterial({
      color: 0xdfe9ff,
      transparent: true,
      opacity: 0.22,
      roughness: 0.12,
      metalness: 0.05,
      transmission: 0.82,
      thickness: 1.8,
      emissive: 0x8097ff,
      emissiveIntensity: 0.15,
    });

    const ringMaterial = new THREE.MeshBasicMaterial({
      color: 0xc7ecff,
      transparent: true,
      opacity: 0.34,
      wireframe: true,
    });

    const coreTorus = new THREE.Mesh(new THREE.TorusKnotGeometry(2.25, 0.34, 210, 26), glassMaterial);
    const wireRing = new THREE.Mesh(new THREE.TorusGeometry(3.6, 0.05, 16, 140), ringMaterial);
    wireRing.rotation.x = Math.PI / 2.65;
    const halo = new THREE.Mesh(
      new THREE.TorusGeometry(4.9, 0.08, 12, 120),
      new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.12 })
    );
    halo.rotation.x = Math.PI / 2.4;
    core.add(coreTorus, wireRing, halo);

    const shardGroup = new THREE.Group();
    scene.add(shardGroup);
    const shardGeometry = new THREE.BoxGeometry(0.5, 2.5, 0.18);
    const shardMaterial = new THREE.MeshPhysicalMaterial({
      color: 0xf1f6ff,
      transparent: true,
      opacity: 0.18,
      roughness: 0.06,
      metalness: 0.45,
      transmission: 0.5,
      emissive: 0x9cb4ff,
      emissiveIntensity: 0.12,
    });
    const shards: THREE.Mesh[] = [];
    for (let i = 0; i < 14; i += 1) {
      const shard = new THREE.Mesh(shardGeometry, shardMaterial);
      const angle = (i / 14) * Math.PI * 2;
      const radius = 5.1 + (i % 3) * 0.55;
      shard.position.set(Math.cos(angle) * radius, (i % 5) - 2, Math.sin(angle) * radius * 0.48);
      shard.rotation.set((i % 4) * 0.4, angle, Math.PI / 10);
      shard.scale.set(1, 0.85 + (i % 4) * 0.18, 1);
      shardGroup.add(shard);
      shards.push(shard);
    }

    const silhouette = new THREE.Group();
    scene.add(silhouette);
    silhouette.position.set(0.25, -1.35, 1.2);
    silhouette.rotation.set(-0.18, -0.55, 0.16);
    const silhouetteMaterial = new THREE.MeshStandardMaterial({
      color: 0xd8dde5,
      roughness: 0.34,
      metalness: 0.78,
      emissive: 0x8f9aa6,
      emissiveIntensity: 0.05,
    });
    const addPart = (geo: THREE.BufferGeometry, x: number, y: number, z: number, rx = 0, ry = 0, rz = 0) => {
      const mesh = new THREE.Mesh(geo, silhouetteMaterial);
      mesh.position.set(x, y, z);
      mesh.rotation.set(rx, ry, rz);
      silhouette.add(mesh);
    };
    addPart(new THREE.BoxGeometry(5.8, 0.34, 0.42), 0, 0, 0);
    addPart(new THREE.BoxGeometry(1.55, 0.92, 0.38), -1.8, -0.38, 0.05, 0, 0, -0.24);
    addPart(new THREE.BoxGeometry(1.95, 0.34, 0.34), 2.5, 0, 0);
    addPart(new THREE.CylinderGeometry(0.08, 0.08, 2.8, 18), 3.9, -0.02, 0, 0, 0, Math.PI / 2);
    addPart(new THREE.BoxGeometry(0.7, 0.55, 0.26), 0.85, 0.34, 0, 0, 0, 0.08);
    addPart(new THREE.BoxGeometry(1.55, 0.26, 0.26), -0.4, -0.42, 0, 0, 0, -0.62);

    const scanGroup = new THREE.Group();
    scene.add(scanGroup);
    const lineMaterial = new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.14 });
    for (let i = 0; i < 6; i += 1) {
      const points = [
        new THREE.Vector3(-7.5 + i * 0.8, -4.3 + i * 0.55, -7),
        new THREE.Vector3(6.5 - i * 0.65, -3.4 + i * 0.45, 3),
      ];
      const geometry = new THREE.BufferGeometry().setFromPoints(points);
      const line = new THREE.Line(geometry, lineMaterial);
      scanGroup.add(line);
    }

    let raf = 0;
    let disposed = false;
    const start = performance.now();
    const animate = (t: number) => {
      if (disposed) return;
      const elapsed = (t - start) * 0.001;

      core.rotation.y = elapsed * 0.28;
      core.rotation.x = Math.sin(elapsed * 0.6) * 0.15;
      wireRing.rotation.z += 0.0032;
      halo.rotation.z -= 0.0018;
      shardGroup.rotation.y = -elapsed * 0.14;
      shardGroup.rotation.z = Math.sin(elapsed * 0.34) * 0.08;
      silhouette.rotation.y = -0.55 + Math.sin(elapsed * 0.38) * 0.16;
      silhouette.position.y = -1.35 + Math.sin(elapsed * 0.8) * 0.18;
      shards.forEach((shard, index) => {
        shard.position.y += Math.sin(elapsed * 0.9 + index) * 0.004;
        shard.rotation.x += 0.002 + index * 0.00002;
      });
      camera.position.x = Math.sin(elapsed * 0.22) * 0.85;
      camera.position.y = 0.8 + Math.cos(elapsed * 0.3) * 0.28;
      camera.lookAt(0, 0.25, 0);

      renderer.render(scene, camera);
      raf = requestAnimationFrame(animate);
    };
    raf = requestAnimationFrame(animate);

    const resizeObserver = new ResizeObserver(() => {
      const width = mount.clientWidth;
      const height = Math.max(mount.clientHeight, 1);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height);
    });
    resizeObserver.observe(mount);

    return () => {
      disposed = true;
      cancelAnimationFrame(raf);
      resizeObserver.disconnect();
      scene.traverse((obj) => {
        const geometry = (obj as THREE.Mesh).geometry as THREE.BufferGeometry | undefined;
        if (geometry) geometry.dispose();
        const material = (obj as THREE.Mesh).material as THREE.Material | THREE.Material[] | undefined;
        if (material) {
          if (Array.isArray(material)) material.forEach((m) => m.dispose());
          else material.dispose();
        }
      });
      renderer.dispose();
      mount.innerHTML = "";
    };
  }, [reducedMotion]);

  return <div ref={mountRef} className="hero-portal-scene" aria-hidden />;
}
