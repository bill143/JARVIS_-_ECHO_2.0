/* JARVIS home sphere: a Three.js particle shell that breathes with his voice.
 *
 * window.JarvisSphere.create(canvas) -> { setState(state), setLevel(level), fps(), destroy() }
 *   state: "listening" | "thinking" | "speaking" | "muted" | "offline" | "starting"
 *   level: 0..1, the live audio level (JARVIS's output while speaking, the mic otherwise)
 *
 * Three.js r169 is vendored (static/vendor) so the console works offline.
 */
import * as THREE from "/static/vendor/three-0.169.0.module.min.js";

const PARTICLES = 4200;
const SHELL_RADIUS = 1.0;
const SHELL_DEPTH = 0.06;
const MAX_PIXEL_RATIO = 2;
const CAMERA_Z = 4.4;  // sphere fills about half the window height, leaving room for captions

// Colour and motion per state. Calm when idle, alive when talking.
const LOOK = {
  starting:  { color: 0x2b6cb0, spin: 0.05, gain: 0.0, glow: 0.55 },
  listening: { color: 0x4fc3ff, spin: 0.06, gain: 0.30, glow: 0.80 },
  thinking:  { color: 0x8fd8ff, spin: 0.30, gain: 0.10, glow: 0.95 },
  speaking:  { color: 0x00e5ff, spin: 0.10, gain: 0.55, glow: 1.00 },
  muted:     { color: 0x5a6b85, spin: 0.03, gain: 0.0, glow: 0.45 },
  offline:   { color: 0x7a3b4a, spin: 0.02, gain: 0.0, glow: 0.35 },
};

function particleSprite() {
  const size = 64;
  const c = document.createElement("canvas");
  c.width = size; c.height = size;
  const g = c.getContext("2d");
  const grad = g.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  grad.addColorStop(0, "rgba(255,255,255,1)");
  grad.addColorStop(0.25, "rgba(200,240,255,0.85)");
  grad.addColorStop(0.6, "rgba(120,200,255,0.18)");
  grad.addColorStop(1, "rgba(0,0,0,0)");
  g.fillStyle = grad;
  g.fillRect(0, 0, size, size);
  return new THREE.CanvasTexture(c);
}

function shellPoints(count) {
  const base = new Float32Array(count * 3);
  const seed = new Float32Array(count);
  // Fibonacci sphere: even coverage, no clumps at the poles.
  const golden = Math.PI * (3 - Math.sqrt(5));
  for (let i = 0; i < count; i++) {
    const y = 1 - (i / (count - 1)) * 2;
    const ring = Math.sqrt(1 - y * y);
    const theta = golden * i;
    const r = SHELL_RADIUS + (Math.random() - 0.5) * SHELL_DEPTH;
    base[i * 3] = Math.cos(theta) * ring * r;
    base[i * 3 + 1] = y * r;
    base[i * 3 + 2] = Math.sin(theta) * ring * r;
    seed[i] = Math.random() * Math.PI * 2;
  }
  return { base, seed };
}

function create(canvas) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: "high-performance" });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, MAX_PIXEL_RATIO));
  renderer.setClearColor(0x000000, 0);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 50);
  camera.position.set(0, 0, CAMERA_Z);

  const { base, seed } = shellPoints(PARTICLES);
  const positions = new Float32Array(base);
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  const sprite = particleSprite();
  const material = new THREE.PointsMaterial({
    color: LOOK.starting.color, size: 0.028, map: sprite, transparent: true,
    opacity: 0.85, depthWrite: false, blending: THREE.AdditiveBlending, sizeAttenuation: true,
  });
  const shell = new THREE.Points(geometry, material);
  scene.add(shell);

  // A faint inner lattice gives the sphere depth without stealing focus.
  const lattice = new THREE.LineSegments(
    new THREE.WireframeGeometry(new THREE.IcosahedronGeometry(0.62, 2)),
    new THREE.LineBasicMaterial({ color: 0x4fc3ff, transparent: true, opacity: 0.07, blending: THREE.AdditiveBlending, depthWrite: false }),
  );
  scene.add(lattice);

  const halo = new THREE.Sprite(new THREE.SpriteMaterial({
    map: sprite, color: 0x1e88e5, transparent: true, opacity: 0.22, depthWrite: false, blending: THREE.AdditiveBlending,
  }));
  halo.scale.set(3.4, 3.4, 1);
  scene.add(halo);

  let state = "starting";
  let target = 0;
  let level = 0;
  let rafId = 0;
  let last = performance.now();
  let time = 0;
  const color = new THREE.Color(LOOK.starting.color);
  const wanted = new THREE.Color(LOOK.starting.color);
  const fps = { frames: 0, since: last, value: 0 };

  function resize() {
    const w = canvas.clientWidth || window.innerWidth;
    const h = canvas.clientHeight || window.innerHeight;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    // Keep the sphere a similar share of the shorter side whatever the window shape.
    camera.position.z = w >= h ? CAMERA_Z : CAMERA_Z * (h / w);
    camera.updateProjectionMatrix();
  }

  function frame(now) {
    const dt = Math.min(0.05, (now - last) / 1000);
    last = now;
    time += dt;
    const look = LOOK[state] || LOOK.listening;
    level += (target * look.gain - level) * Math.min(1, dt * 12);
    target *= Math.pow(0.04, dt);  // levels fade unless the stream keeps them up

    // Breathing radius plus a ripple that travels over the shell with the voice.
    const breathe = 1 + Math.sin(time * 0.9) * 0.012 + level * 0.18;
    const ripple = 0.015 + level * 0.12;
    const speed = 1.4 + level * 5;
    for (let i = 0; i < PARTICLES; i++) {
      const k = i * 3;
      const s = breathe + Math.sin(seed[i] + time * speed + base[k + 1] * 4) * ripple;
      positions[k] = base[k] * s;
      positions[k + 1] = base[k + 1] * s;
      positions[k + 2] = base[k + 2] * s;
    }
    geometry.attributes.position.needsUpdate = true;

    shell.rotation.y += dt * look.spin;
    shell.rotation.x = Math.sin(time * 0.15) * 0.18;
    lattice.rotation.y -= dt * look.spin * 0.6;
    lattice.rotation.z += dt * look.spin * 0.25;

    wanted.setHex(look.color);
    color.lerp(wanted, Math.min(1, dt * 3));
    material.color.copy(color);
    lattice.material.color.copy(color);
    material.opacity = 0.55 + look.glow * 0.3 + level * 0.15;
    halo.material.opacity = 0.12 + look.glow * 0.1 + level * 0.35;
    material.size = 0.024 + level * 0.016;

    renderer.render(scene, camera);

    fps.frames += 1;
    if (now - fps.since >= 1000) {
      fps.value = Math.round((fps.frames * 1000) / (now - fps.since));
      fps.frames = 0;
      fps.since = now;
      canvas.dataset.fps = String(fps.value);  // read by the browser checks
    }
    rafId = requestAnimationFrame(frame);
  }

  resize();
  window.addEventListener("resize", resize);
  rafId = requestAnimationFrame(frame);

  return {
    setState(next) { state = LOOK[next] ? next : "listening"; },
    setLevel(value) { target = Math.max(target, Math.min(1, Math.max(0, Number(value) || 0))); },
    fps() { return fps.value; },
    destroy() {
      cancelAnimationFrame(rafId);
      window.removeEventListener("resize", resize);
      geometry.dispose(); material.dispose(); sprite.dispose(); renderer.dispose();
    },
  };
}

window.JarvisSphere = { create };
