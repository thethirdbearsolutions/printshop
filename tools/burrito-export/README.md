# burrito-export

Builds Chaotic Attack burritos headlessly and dumps their parts for `printshop burrito`.

```bash
cd tools/burrito-export
npm install                      # three 0.170.0, the version chaotic-attack locks
node --experimental-strip-types export.mjs ../../../chaotic-attack ../../printshop/data/burritos madison yuri --hero
```

It copies `src/burrito.ts` out of a chaotic-attack checkout (Node 22 strips the types; nothing in
chaotic-attack changes), stubs the browser canvas the textures are painted on (`canvas.mjs` tallies the
area painted in each colour instead of drawing), seeds `Math.random` so sprinkles and doodles land the same
way each run, and calls `buildBurrito(kind, hero)`. Every visible mesh becomes a part:

- `type`, `params`: the three.js geometry and its parameters;
- `matrix`: its world matrix (column-major, as three.js keeps it);
- `colour`: the material colour times the dominant paint of its texture, and `palette`, the texture's colours by
  share of paint;
- `double_sided`: three.js's mark of a sheet (capes, lenses), which printshop thickens;
- `triangles`: world-space triangles, y up, facing -z. Stock primitives nobody edited after building
  (spheres, capsules, cylinders, cones, tori) are rebuilt with more segments first, so prints are smooth.

`OUT_DIR/<kind>[-hero].json.gz`. With no kinds it exports all of them.
