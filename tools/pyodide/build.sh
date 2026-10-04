#!/usr/bin/env bash
# Build manifold3d as a Pyodide (WebAssembly) wheel, so printshop runs in a browser.
#
#   tools/pyodide/build.sh [WORK_DIR]        -> tools/pyodide/dist/manifold3d-*-pyemscripten_*_wasm32.whl
#
# Pyodide 0.29.5 (Python 3.13, Emscripten 4.0.9). Needs python3.13, git, cmake and ninja; downloads
# pyodide-build, its cross-build environment and emsdk (about 1.5 GB) into WORK_DIR. Set EMSDK_DIR to
# reuse an emsdk checkout. manifold3d-3.5.4-pyodide.patch is all that changes upstream:
#   - an option, MANIFOLD_PYODIDE, that builds the Python bindings under Emscripten (upstream only
#     builds them natively) without the standalone-app link flags its Emscripten build adds;
#   - no Python stub generation then (it imports the module with the build machine's Python);
#   - the parallel backend (TBB) off: one thread in the browser;
#   - two size_t casts in the bindings, which are 32-bit on wasm32.
set -euo pipefail
PYODIDE=0.29.5 EMSCRIPTEN=4.0.9 MANIFOLD=3.5.4
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="$(mkdir -p "${1:-$HERE/.work}" && cd "${1:-$HERE/.work}" && pwd)"
cd "$WORK"
[ -d venv ] || python3.13 -m venv venv
. venv/bin/activate
pip install -q pyodide-build
pyodide xbuildenv install "$PYODIDE"
EMSDK_DIR="${EMSDK_DIR:-$WORK/emsdk}"
[ -d "$EMSDK_DIR" ] || git clone -q --depth 1 https://github.com/emscripten-core/emsdk.git "$EMSDK_DIR"
(cd "$EMSDK_DIR" && ./emsdk install "$EMSCRIPTEN" >/dev/null && ./emsdk activate "$EMSCRIPTEN" >/dev/null)
. "$EMSDK_DIR/emsdk_env.sh" >/dev/null 2>&1
rm -rf "manifold3d-$MANIFOLD"
pip download -q --no-binary :all: --no-deps "manifold3d==$MANIFOLD" -d .
tar xzf "manifold3d-$MANIFOLD.tar.gz"
cd "manifold3d-$MANIFOLD"
patch -p1 < "$HERE/manifold3d-$MANIFOLD-pyodide.patch"
pyodide build . -o "$HERE/dist" \
  -C cmake.define.MANIFOLD_PYODIDE=ON -C cmake.define.MANIFOLD_JSBIND=OFF \
  -C cmake.define.MANIFOLD_USE_BUILTIN_CLIPPER2=ON
ls -la "$HERE/dist"
