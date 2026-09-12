import * as THREE from "https://cdn.jsdelivr.net/npm/three@0.180.0/build/three.module.js";
import { EffectComposer } from "https://cdn.jsdelivr.net/npm/three@0.180.0/examples/jsm/postprocessing/EffectComposer.js";
import { RenderPass } from "https://cdn.jsdelivr.net/npm/three@0.180.0/examples/jsm/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "https://cdn.jsdelivr.net/npm/three@0.180.0/examples/jsm/postprocessing/UnrealBloomPass.js";

// Standalone 3D hologram renderer integrated into Shadow.
// It intentionally has no orange ground shadow/disc and the projection
// rings are centered around the core instead of hanging below it.

export function createHologram(canvas, { stage = canvas.parentElement } = {}) {
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x010202);
  scene.fog = new THREE.FogExp2(0x010202, 0.035);

  const camera = new THREE.PerspectiveCamera(48, 1, 0.1, 100);
  camera.position.set(0, 0.25, 8.5);

  const renderer = new THREE.WebGLRenderer({
    canvas,
    antialias: true,
    alpha: false,
    powerPreference: "high-performance",
  });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setSize(1, 1, false);
  renderer.outputColorSpace = THREE.SRGBColorSpace;

  const composer = new EffectComposer(renderer);
  composer.addPass(new RenderPass(scene, camera));

  const bloom = new UnrealBloomPass(new THREE.Vector2(1, 1), 1.35, 0.65, 0.12);
  composer.addPass(bloom);

  const gold = new THREE.Color(0xff9a32);
  const bright = new THREE.Color(0xffd36a);
  const darkGold = new THREE.Color(0x7d3d13);

  const holo = new THREE.Group();
  scene.add(holo);

  const lineMaterial = (opacity = 0.65) => new THREE.LineBasicMaterial({
    color: gold,
    transparent: true,
    opacity,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });

  const glowMaterial = (color = bright, opacity = 0.9) => new THREE.MeshBasicMaterial({
    color,
    transparent: true,
    opacity,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });

  // ---- central projection core ----
  const coreGroup = new THREE.Group();
  holo.add(coreGroup);

  const core = new THREE.Mesh(
    new THREE.IcosahedronGeometry(0.62, 2),
    new THREE.MeshBasicMaterial({
      color: bright,
      wireframe: true,
      transparent: true,
      opacity: 0.72,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    })
  );
  coreGroup.add(core);

  const innerCore = new THREE.Mesh(
    new THREE.IcosahedronGeometry(0.29, 1),
    glowMaterial(bright, 0.25)
  );
  coreGroup.add(innerCore);

  const centerOrb = new THREE.Mesh(
    new THREE.SphereGeometry(0.12, 24, 24),
    glowMaterial(0xffffff, 1)
  );
  coreGroup.add(centerOrb);

  // ---- holographic shell ----
  const sphere = new THREE.Mesh(
    new THREE.SphereGeometry(2.35, 48, 32),
    new THREE.MeshBasicMaterial({
      color: gold,
      wireframe: true,
      transparent: true,
      opacity: 0.12,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    })
  );
  holo.add(sphere);

  const sphere2 = new THREE.Mesh(
    new THREE.IcosahedronGeometry(2.7, 2),
    new THREE.MeshBasicMaterial({
      color: darkGold,
      wireframe: true,
      transparent: true,
      opacity: 0.11,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    })
  );
  holo.add(sphere2);

  // ---- centered orbital rings ----
  function makeRing(radius, tube, rotation, opacity = 0.5) {
    const ring = new THREE.Mesh(
      new THREE.TorusGeometry(radius, tube, 8, 160),
      lineMaterial(opacity)
    );
    ring.rotation.set(...rotation);
    holo.add(ring);
    return ring;
  }

  const rings = [
    makeRing(1.05, 0.014, [0.2, 0.0, 0.0], 0.78),
    makeRing(1.45, 0.011, [Math.PI / 2, 0.3, 0.2], 0.58),
    makeRing(1.9, 0.008, [0.9, 0.2, Math.PI / 3], 0.43),
    makeRing(2.35, 0.006, [1.35, -0.4, 0.8], 0.28),
  ];

  // ---- projection beams ----
  const beamGroup = new THREE.Group();
  holo.add(beamGroup);

  for (let i = 0; i < 70; i++) {
    const direction = new THREE.Vector3(
      THREE.MathUtils.randFloatSpread(2),
      THREE.MathUtils.randFloatSpread(2),
      THREE.MathUtils.randFloatSpread(2)
    ).normalize();
    const length = THREE.MathUtils.randFloat(2.8, 5.5);
    const geometry = new THREE.BufferGeometry().setFromPoints([
      direction.clone().multiplyScalar(0.2),
      direction.clone().multiplyScalar(length),
    ]);
    beamGroup.add(new THREE.Line(
      geometry,
      lineMaterial(THREE.MathUtils.randFloat(0.07, 0.20))
    ));
  }

  // ---- particles ----
  const particleCount = 1800;
  const positions = new Float32Array(particleCount * 3);
  const particleData = [];

  for (let i = 0; i < particleCount; i++) {
    const r = Math.pow(Math.random(), 0.55) * 4.2 + 0.25;
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos(THREE.MathUtils.randFloatSpread(2));
    positions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
    positions[i * 3 + 1] = r * Math.cos(phi);
    positions[i * 3 + 2] = r * Math.sin(phi) * Math.sin(theta);
    particleData.push({ radius: r, phase: Math.random() * Math.PI * 2, speed: THREE.MathUtils.randFloat(0.1, 0.55) });
  }

  const particleGeometry = new THREE.BufferGeometry();
  particleGeometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));

  const textureCanvas = document.createElement("canvas");
  textureCanvas.width = 64;
  textureCanvas.height = 64;
  const pctx = textureCanvas.getContext("2d");
  const gradient = pctx.createRadialGradient(32, 32, 0, 32, 32, 32);
  gradient.addColorStop(0, "rgba(255,255,255,1)");
  gradient.addColorStop(0.18, "rgba(255,190,80,0.9)");
  gradient.addColorStop(0.5, "rgba(255,120,20,0.25)");
  gradient.addColorStop(1, "rgba(255,80,0,0)");
  pctx.fillStyle = gradient;
  pctx.fillRect(0, 0, 64, 64);
  const particleTexture = new THREE.CanvasTexture(textureCanvas);

  const particles = new THREE.Points(
    particleGeometry,
    new THREE.PointsMaterial({
      color: 0xffa23c,
      size: 0.035,
      map: particleTexture,
      transparent: true,
      opacity: 0.72,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      sizeAttenuation: true,
    })
  );
  holo.add(particles);

  // ---- scanning layers ----
  const scanGroup = new THREE.Group();
  holo.add(scanGroup);
  for (let i = 0; i < 3; i++) {
    const plane = new THREE.Mesh(
      new THREE.PlaneGeometry(5.4, 0.018),
      new THREE.MeshBasicMaterial({
        color: bright,
        transparent: true,
        opacity: 0.2,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
        side: THREE.DoubleSide,
      })
    );
    plane.position.y = -1 + i * 1;
    plane.rotation.y = Math.random() * 0.7;
    scanGroup.add(plane);
  }

  // ---- fragmented data arcs ----
  const arcGroup = new THREE.Group();
  holo.add(arcGroup);
  for (let i = 0; i < 18; i++) {
    const radius = THREE.MathUtils.randFloat(1.2, 3.3);
    const points = [];
    const start = Math.random() * Math.PI * 2;
    const sweep = THREE.MathUtils.randFloat(0.15, 0.8);
    for (let j = 0; j < 28; j++) {
      const t = j / 27;
      const a = start + sweep * t;
      const wobble = 1 + Math.sin(t * 14 + i) * 0.015;
      points.push(new THREE.Vector3(
        Math.cos(a) * radius * wobble,
        THREE.MathUtils.randFloatSpread(0.7),
        Math.sin(a) * radius * wobble
      ));
    }
    const arc = new THREE.Line(
      new THREE.BufferGeometry().setFromPoints(points),
      lineMaterial(THREE.MathUtils.randFloat(0.18, 0.55))
    );
    arc.rotation.x = THREE.MathUtils.randFloat(-1, 1);
    arc.rotation.z = THREE.MathUtils.randFloat(-1, 1);
    arcGroup.add(arc);
  }

  // IMPORTANT: no base disc / ground shadow. The emitter is centered
  // around y=0 so its rings belong to the projection instead of sitting
  // underneath it.
  const emitter = new THREE.Group();
  holo.add(emitter);
  const emitterRing = new THREE.Mesh(
    new THREE.TorusGeometry(1.65, 0.026, 8, 120),
    glowMaterial(gold, 0.42)
  );
  const emitterRing2 = new THREE.Mesh(
    new THREE.TorusGeometry(2.05, 0.012, 8, 120),
    glowMaterial(gold, 0.22)
  );
  emitter.add(emitterRing, emitterRing2);

  // ---- interaction ----
  let targetRotationX = -0.08;
  let targetRotationY = 0.35;
  let rotationX = targetRotationX;
  let rotationY = targetRotationY;
  let zoomTarget = 8.5;
  let zoom = zoomTarget;
  let dragging = false;
  let lastX = 0;
  let lastY = 0;
  let state = "idle";
  const stateColors = {
    idle: 0xffd36a,
    listening: 0x4de1d0,
    thinking: 0xa78bfa,
    searching: 0x55b7ff,
    executing: 0xffa23c,
    waiting_confirmation: 0xffd166,
    speaking: 0xff9a32,
    error: 0xff6b6b,
  };
  const activeStateColor = new THREE.Color(stateColors.idle);
  let disposed = false;

  const pointerDown = (event) => {
    dragging = true;
    lastX = event.clientX;
    lastY = event.clientY;
    try { canvas.setPointerCapture(event.pointerId); } catch (_) {}
  };

  const pointerMove = (event) => {
    if (!dragging) return;
    const dx = event.clientX - lastX;
    const dy = event.clientY - lastY;
    targetRotationY += dx * 0.008;
    targetRotationX += dy * 0.006;
    targetRotationX = THREE.MathUtils.clamp(targetRotationX, -1.3, 1.3);
    lastX = event.clientX;
    lastY = event.clientY;
  };

  const pointerUp = () => { dragging = false; };

  const wheel = (event) => {
    event.preventDefault();
    zoomTarget = THREE.MathUtils.clamp(zoomTarget + event.deltaY * 0.005, 4.2, 14);
  };

  const dblclick = () => {
    targetRotationX = -0.08;
    targetRotationY = 0.35;
    zoomTarget = 8.5;
  };

  canvas.addEventListener("pointerdown", pointerDown);
  canvas.addEventListener("pointermove", pointerMove);
  canvas.addEventListener("pointerup", pointerUp);
  canvas.addEventListener("pointercancel", pointerUp);
  canvas.addEventListener("wheel", wheel, { passive: false });
  canvas.addEventListener("dblclick", dblclick);

  function resize() {
    const rect = canvas.getBoundingClientRect();
    const width = Math.max(1, rect.width || stage?.clientWidth || window.innerWidth);
    const height = Math.max(1, rect.height || stage?.clientHeight || window.innerHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setSize(width, height, false);
    composer.setSize(width, height);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
  }

  const resizeObserver = typeof ResizeObserver !== "undefined"
    ? new ResizeObserver(resize)
    : null;
  resizeObserver?.observe(stage || canvas);
  window.addEventListener("resize", resize);

  const clock = new THREE.Clock();
  let frame = 0;

  function animate() {
    if (disposed) return;
    frame = requestAnimationFrame(animate);
    const elapsed = clock.getElapsedTime();
    const pulse = (Math.sin(elapsed * 3.2) + 1) / 2;
    const stateGlow = {
      idle: 1,
      listening: 1.3,
      thinking: 1.15,
      searching: 1.35,
      executing: 1.5,
      waiting_confirmation: 1.45,
      speaking: 1.6,
      error: 0.8,
    }[state] || 1;
    activeStateColor.setHex(stateColors[state] || stateColors.idle);
    core.material.color.lerp(activeStateColor, 0.08);
    innerCore.material.color.lerp(activeStateColor, 0.08);

    rotationX = THREE.MathUtils.lerp(rotationX, targetRotationX, 0.08);
    rotationY = THREE.MathUtils.lerp(rotationY, targetRotationY, 0.08);
    zoom = THREE.MathUtils.lerp(zoom, zoomTarget, 0.08);

    holo.rotation.x = rotationX;
    holo.rotation.y = rotationY;

    sphere.rotation.y = elapsed * 0.16;
    sphere.rotation.z = elapsed * 0.08;
    sphere2.rotation.x = -elapsed * 0.11;
    sphere2.rotation.y = elapsed * 0.21;

    core.rotation.x = elapsed * 0.6;
    core.rotation.y = elapsed * 0.9;
    innerCore.rotation.x = -elapsed * 0.8;
    innerCore.rotation.z = elapsed * 0.5;
    coreGroup.scale.setScalar(1 + pulse * 0.045 * stateGlow);

    rings[0].rotation.z = elapsed * 0.8;
    rings[1].rotation.x = elapsed * 0.45;
    rings[2].rotation.y = -elapsed * 0.3;
    rings[3].rotation.z = -elapsed * 0.18;

    beamGroup.rotation.y = -elapsed * 0.04;
    beamGroup.rotation.x = Math.sin(elapsed * 0.2) * 0.08;
    arcGroup.rotation.y = elapsed * 0.08;
    arcGroup.rotation.x = Math.sin(elapsed * 0.13) * 0.1;
    scanGroup.position.y = Math.sin(elapsed * 0.7) * 0.35;
    emitterRing.rotation.z = elapsed * 0.65;
    emitterRing2.rotation.z = -elapsed * 0.35;

    const pos = particleGeometry.attributes.position.array;
    for (let i = 0; i < particleCount; i++) {
      const p = particleData[i];
      const angle = p.phase + elapsed * p.speed;
      pos[i * 3] = Math.cos(angle) * p.radius + Math.sin(elapsed * 0.8 + i) * 0.025;
      pos[i * 3 + 2] = Math.sin(angle) * p.radius + Math.cos(elapsed * 0.6 + i) * 0.025;
      pos[i * 3 + 1] += Math.sin(elapsed * p.speed + p.phase) * 0.0008;
    }
    particleGeometry.attributes.position.needsUpdate = true;

    camera.position.z = zoom;
    camera.position.x = Math.sin(elapsed * 0.12) * 0.08;
    camera.lookAt(0, 0, 0);

    bloom.strength = 1.25 + pulse * 0.28 * stateGlow;
    composer.render();
  }

  const api = {
    resize,
    setState(nextState) {
      state = nextState || "idle";
    },
    dispose() {
      disposed = true;
      cancelAnimationFrame(frame);
      resizeObserver?.disconnect();
      window.removeEventListener("resize", resize);
      canvas.removeEventListener("pointerdown", pointerDown);
      canvas.removeEventListener("pointermove", pointerMove);
      canvas.removeEventListener("pointerup", pointerUp);
      canvas.removeEventListener("pointercancel", pointerUp);
      canvas.removeEventListener("wheel", wheel);
      canvas.removeEventListener("dblclick", dblclick);
      composer.dispose();
      renderer.dispose();
    },
  };

  resize();
  animate();
  return api;
}
