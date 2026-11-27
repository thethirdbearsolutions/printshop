// Dump Chaotic Attack burritos as coloured triangle soup for printshop.
//
//   npx tsx tools/dump_burrito.mts ../chaotic-attack yuri madison --out burritos/
//   npx tsx tools/dump_burrito.mts ../chaotic-attack --all --hero --out burritos/
//
// Each burrito becomes <out>/<kind>.json: {kind, name, hero, up:"y", meshes:[{color, positions, index}]},
// positions already in world space (the burrito's group transform applied), in game units.
// The game's chaotic-attack checkout needs `npm install` first, so `three` resolves.
//
// buildBurrito() paints a few wraps with canvas textures (rainbow, sweater, leopard...). There is
// no canvas in Node, so a stand-in 2D context records how much area each fill colour covers, and
// the mesh takes the texture's dominant colour times the material colour. Patterns don't print
// as patterns; the main colour does.
import { mkdirSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

// ---- a canvas stand-in that only keeps score of colours -------------------------------------
function parseColour(s: unknown): [number, number, number] | null {
  if (typeof s !== 'string') return null;
  const t = s.trim().toLowerCase();
  let m = t.match(/^#([0-9a-f]{6})$/);
  if (m) { const n = parseInt(m[1], 16); return [(n >> 16) & 255, (n >> 8) & 255, n & 255]; }
  m = t.match(/^#([0-9a-f]{3})$/);
  if (m) return [0, 1, 2].map((i) => parseInt(m![1][i] + m![1][i], 16)) as [number, number, number];
  m = t.match(/^rgba?\(([^)]+)\)$/);
  if (m) { const p = m[1].split(',').map((x) => parseFloat(x)); return [p[0], p[1], p[2]]; }
  m = t.match(/^hsla?\(([^)]+)\)$/);
  if (m) {
    const p = m[1].replace(/%/g, '').split(/[ ,/]+/).filter(Boolean).map(parseFloat);
    const h = (((p[0] % 360) + 360) % 360) / 360, s2 = p[1] / 100, l = p[2] / 100;
    const q = l < 0.5 ? l * (1 + s2) : l + s2 - l * s2, pp = 2 * l - q;
    const f = (tt: number) => { tt = (tt + 1) % 1; return tt < 1 / 6 ? pp + (q - pp) * 6 * tt : tt < 0.5 ? q : tt < 2 / 3 ? pp + (q - pp) * (2 / 3 - tt) * 6 : pp; };
    return [f(h + 1 / 3) * 255, f(h) * 255, f(h - 1 / 3) * 255];
  }
  return null;
}

class FakeCanvas {
  width = 300; height = 150;
  areas = new Map<string, number>();
  getContext() {
    const canvas = this;
    let fill: unknown = '#ffffff';
    const add = (a: number) => {
      const c = parseColour(fill);
      if (!c) return;
      const k = c.map((x) => Math.round(x)).join(',');
      canvas.areas.set(k, (canvas.areas.get(k) ?? 0) + Math.abs(a));
    };
    const target: Record<string, unknown> = {
      fillRect: (_x: number, _y: number, w: number, h: number) => add(w * h),
      fill: () => add(canvas.width * canvas.height * 0.02), // a shape of unknown size: a small vote
      createLinearGradient: () => ({ addColorStop: (_o: number, c: string) => { fill = c; add(canvas.width * canvas.height * 0.05); } }),
      createRadialGradient: () => ({ addColorStop: (_o: number, c: string) => { fill = c; add(canvas.width * canvas.height * 0.05); } }),
      measureText: () => ({ width: 0 }),
      getImageData: (_x: number, _y: number, w: number, h: number) => ({ data: new Uint8ClampedArray(w * h * 4), width: w, height: h }),
      createImageData: (w: number, h: number) => ({ data: new Uint8ClampedArray(w * h * 4), width: w, height: h }),
    };
    return new Proxy(target, {
      get: (t, k) => (k in t ? t[k as string] : k === 'fillStyle' ? fill : () => undefined),
      set: (t, k, v) => { if (k === 'fillStyle') fill = v; else t[k as string] = v; return true; },
    });
  }
  dominant(): [number, number, number] | null {
    let best: string | null = null, area = -1;
    for (const [k, a] of this.areas) if (a > area) { best = k; area = a; }
    return best ? (best.split(',').map(Number) as [number, number, number]) : null;
  }
}
(globalThis as any).document = {
  createElement: (tag: string) => (tag === 'canvas' ? new FakeCanvas() : {}),
};

// ---- the same burrito every time --------------------------------------------------------------
function seeded(seed: number) {
  return () => { seed |= 0; seed = (seed + 0x6d2b79f5) | 0; let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}

const args = process.argv.slice(2);
const game = resolve(args.shift() ?? '');
const hero = args.includes('--hero');
const all = args.includes('--all');
const oi = args.indexOf('--out');
const out = oi >= 0 ? args[oi + 1] : '.';
const kinds = args.filter((a, i) => !a.startsWith('--') && args[i - 1] !== '--out');

const mod = await import(pathToFileURL(join(game, 'src', 'burrito.ts')).href);
const THREE = await import(pathToFileURL(join(game, 'node_modules', 'three', 'build', 'three.module.js')).href);
const list: string[] = all ? mod.ALL_BURRITOS : kinds;
if (!list.length) { console.error('name some burritos, or pass --all'); process.exit(2); }
mkdirSync(out, { recursive: true });

const hex = (c: any) => '#' + c.getHexString();
for (const kind of list) {
  Math.random = seeded(1234);
  const b = mod.buildBurrito(kind, hero);
  b.run?.(0, 0); // the standing pose
  b.group.updateMatrixWorld(true);
  const meshes: object[] = [];
  b.group.traverse((o: any) => {
    if (!o.isMesh || !o.visible || !o.geometry?.attributes?.position) return;
    let vis = true;
    for (let p = o; p; p = p.parent) if (p.visible === false) vis = false;
    const m = Array.isArray(o.material) ? o.material[0] : o.material;
    if (!vis || !m || m.visible === false || (m.transparent && m.opacity < 0.15)) return;
    const colour = new THREE.Color(m.color ?? 0xffffff);
    const dom = m.map?.image instanceof FakeCanvas ? m.map.image.dominant() : null;
    if (dom) colour.multiply(new THREE.Color().setRGB(dom[0] / 255, dom[1] / 255, dom[2] / 255, THREE.SRGBColorSpace));
    const pos = o.geometry.attributes.position;
    const v = new THREE.Vector3();
    const positions: number[] = [];
    for (let i = 0; i < pos.count; i++) {
      v.fromBufferAttribute(pos, i).applyMatrix4(o.matrixWorld);
      positions.push(+v.x.toFixed(5), +v.y.toFixed(5), +v.z.toFixed(5));
    }
    const index: number[] = o.geometry.index ? Array.from(o.geometry.index.array as ArrayLike<number>) : [...Array(pos.count).keys()];
    // A mirroring transform turns the mesh inside out; flip the winding back.
    if (o.matrixWorld.determinant() < 0) for (let i = 0; i < index.length; i += 3) [index[i + 1], index[i + 2]] = [index[i + 2], index[i + 1]];
    meshes.push({ name: o.name || o.geometry.type, color: hex(colour), positions, index, doubleSided: m.side === THREE.DoubleSide });
  });
  const file = join(out, `${kind}${hero ? '-hero' : ''}.json`);
  writeFileSync(file, JSON.stringify({ kind, name: mod.BURRITO_NAMES[kind], hero, up: 'y', meshes }));
  console.log(`${file}: ${meshes.length} meshes`);
}
