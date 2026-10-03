// Build Chaotic Attack burritos headlessly (no renderer, no browser) and dump their parts for printshop.
//
//   node export.mjs CHAOTIC_ATTACK_DIR OUT_DIR [kind ...] [--hero]
//
// Copies src/burrito.ts from a chaotic-attack checkout next to this script (so `three` resolves to the
// version pinned here, the same one chaotic-attack locks), stubs the canvas the textures are painted on,
// seeds Math.random so sprinkles and doodles land the same way every time, and calls buildBurrito(kind).
// Each visible mesh becomes a part: its geometry type and parameters, world matrix, a representative
// colour (the material colour times the texture's dominant paint) and its world-space triangles,
// remeshed finer when the geometry is a stock three.js primitive nobody has edited. Writes
// OUT_DIR/<kind>.json.gz. Y is up and the burrito faces -z, as in the game.
import fs from 'node:fs';
import path from 'node:path';
import zlib from 'node:zlib';
import { fileURLToPath } from 'node:url';
import { FakeCanvas, dominant, hex } from './canvas.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
const hero = args.includes('--hero');
const [srcDir, outDir, ...kinds] = args.filter((a) => a !== '--hero');
if (!srcDir || !outDir) {
  console.error('usage: node export.mjs CHAOTIC_ATTACK_DIR OUT_DIR [kind ...] [--hero]');
  process.exit(2);
}

// Seeded Math.random (mulberry32), installed before the game code runs.
let seed = 590;
Math.random = () => {
  seed = (seed + 0x6d2b79f5) | 0;
  let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
  t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
};
globalThis.document = { createElement: (tag) => (tag === 'canvas' ? new FakeCanvas() : {}) };

const stage = path.join(here, '.src');
fs.mkdirSync(stage, { recursive: true });
fs.copyFileSync(path.join(srcDir, 'src', 'burrito.ts'), path.join(stage, 'burrito.ts'));
const THREE = await import('three');
const game = await import(path.join(stage, 'burrito.ts'));

// Segment parameters per stock geometry, and how many to ask for (scaled by the part's size).
const REFINE = {
  SphereGeometry: ['widthSegments', 'heightSegments', 0.5],
  CapsuleGeometry: ['radialSegments', 'capSegments', 0.25],
  CylinderGeometry: ['radialSegments', null, 1],
  ConeGeometry: ['radialSegments', null, 1],
  TorusGeometry: ['tubularSegments', 'radialSegments', 0.4],
  CircleGeometry: ['segments', null, 1],
  LatheGeometry: ['segments', null, 1],
};

function visible(o) {
  for (let p = o; p; p = p.parent) if (!p.visible) return false;
  return true;
}

function colourOf(material) {
  const m = Array.isArray(material) ? material[0] : material;
  const rgb = m.color ? m.color.getHexString() : 'ffffff';
  let paint = null;
  if (m.map && m.map.image instanceof FakeCanvas) paint = dominant(m.map.image);
  const c = new THREE.Color(`#${rgb}`);
  const out = paint ? [c.r * paint.rgb[0] / 255, c.g * paint.rgb[1] / 255, c.b * paint.rgb[2] / 255] : null;
  return {
    colour: out ? hex(out.map((v) => v * 255)) : `#${rgb}`,
    palette: paint ? paint.palette : [],
    opacity: m.transparent ? m.opacity : 1,
  };
}

function sameGeometry(a, b) {
  const pa = a.attributes.position.array, pb = b.attributes.position.array;
  if (pa.length !== pb.length) return false;
  for (let i = 0; i < pa.length; i++) if (Math.abs(pa[i] - pb[i]) > 1e-6) return false;
  return true;
}

/** The mesh's geometry, remeshed finer when it is an unedited stock primitive. */
function fineGeometry(mesh) {
  const g = mesh.geometry;
  const spec = REFINE[g.type];
  if (!spec || !g.parameters || !THREE[g.type]) return g;
  const P = g.parameters;
  const again = new THREE[g.type](...Object.values(P));
  if (!sameGeometry(g, again)) return g; // edited after it was built (translated, bent): keep it as it is
  const s = new THREE.Vector3();
  mesh.matrixWorld.decompose(new THREE.Vector3(), new THREE.Quaternion(), s);
  g.computeBoundingSphere();
  const size = g.boundingSphere.radius * Math.max(s.x, s.y, s.z); // world units; a burrito is about 2 tall
  const n = Math.max(P[spec[0]] || 8, Math.min(64, Math.round((2 * Math.PI * size) / 0.04)));
  const fine = { ...P, [spec[0]]: n };
  if (spec[1]) fine[spec[1]] = Math.max(P[spec[1]] || 1, Math.round(n * spec[2]));
  return new THREE[g.type](...Object.values(fine));
}

function round(v) {
  return Math.round(v * 1e5) / 1e5;
}

function exportBurrito(kind) {
  const b = game.buildBurrito(kind, hero);
  b.group.updateMatrixWorld(true);
  const parts = [];
  let skipped = 0;
  b.group.traverse((o) => {
    if (!o.isMesh) {
      if (o.isPoints || o.isLine || o.isSprite) skipped++;
      return;
    }
    if (!visible(o)) return;
    const fine = fineGeometry(o);
    const geo = fine.index ? fine.toNonIndexed() : fine;
    const pos = geo.attributes.position;
    const v = new THREE.Vector3();
    const world = new Array(pos.count * 3);
    for (let i = 0; i < pos.count; i++) {
      v.fromBufferAttribute(pos, i).applyMatrix4(o.matrixWorld);
      world[3 * i] = round(v.x); world[3 * i + 1] = round(v.y); world[3 * i + 2] = round(v.z);
    }
    const params = {};
    for (const [k, val] of Object.entries(o.geometry.parameters || {})) if (typeof val !== 'object') params[k] = val;
    const side = (Array.isArray(o.material) ? o.material[0] : o.material).side;
    parts.push({
      name: o.name || `${o.geometry.type.replace('Geometry', '').toLowerCase()}${parts.length}`,
      type: o.geometry.type, params, double_sided: side === THREE.DoubleSide,
      matrix: o.matrixWorld.elements.map(round), ...colourOf(o.material), triangles: world,
    });
  });
  return { kind, name: game.BURRITO_NAMES[kind], hero, junior: game.isJunior(kind), up: 'y', facing: '-z',
           three: THREE.REVISION, skipped, parts };
}

fs.mkdirSync(outDir, { recursive: true });
for (const kind of kinds.length ? kinds : game.ALL_BURRITOS) {
  const data = exportBurrito(kind);
  const file = path.join(outDir, `${kind}${hero ? '-hero' : ''}.json.gz`);
  fs.writeFileSync(file, zlib.gzipSync(JSON.stringify(data)));
  console.log(`${file}: ${data.parts.length} parts`);
}
