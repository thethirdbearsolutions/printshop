// A stand-in for the browser's <canvas> 2D context. It draws nothing; it keeps a tally of how much
// area each colour was painted over, so a canvas texture can be given a representative colour.

function parse(style) {
  if (typeof style !== 'string') return null;
  const s = style.trim().toLowerCase();
  let m = s.match(/^#([0-9a-f]{3,8})$/);
  if (m) {
    let h = m[1];
    if (h.length <= 4) h = [...h].map((c) => c + c).join('');
    const a = h.length === 8 ? parseInt(h.slice(6), 16) / 255 : 1;
    return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16), a];
  }
  m = s.match(/^rgba?\(([^)]+)\)$/);
  if (m) {
    const v = m[1].split(/[ ,/]+/).filter(Boolean).map(parseFloat);
    return [v[0], v[1], v[2], v.length > 3 ? v[3] : 1];
  }
  m = s.match(/^hsla?\(([^)]+)\)$/);
  if (m) {
    const [h, sat, l, a = 1] = m[1].split(/[ ,/]+/).filter(Boolean).map(parseFloat);
    const S = sat / 100, L = l / 100, k = (n) => (n + h / 30) % 12;
    const f = (n) => L - S * Math.min(L, 1 - L) * Math.max(-1, Math.min(k(n) - 3, 9 - k(n), 1));
    return [255 * f(0), 255 * f(8), 255 * f(4), a];
  }
  return null;
}

export function hex(rgb) {
  return '#' + rgb.map((v) => Math.max(0, Math.min(255, Math.round(v))).toString(16).padStart(2, '0')).join('');
}

class Gradient {
  constructor() { this.stops = []; }
  addColorStop(_, c) { this.stops.push(c); }
}

class Context2D {
  constructor(canvas) {
    this.canvas = canvas;
    this.fillStyle = '#000000';
    this.strokeStyle = '#000000';
    this.lineWidth = 1;
    this.globalAlpha = 1;
    this.beginPath();
    return new Proxy(this, { get: (t, k) => (k in t ? t[k] : () => undefined) }); // any other call: no-op
  }
  _paint(style, area) {
    const styles = style instanceof Gradient ? style.stops : [style];
    for (const s of styles) {
      const c = parse(s);
      if (!c || area <= 0) continue;
      const key = hex(c.slice(0, 3));
      this.canvas.paint.set(key, (this.canvas.paint.get(key) || 0) + (area * c[3] * this.globalAlpha) / styles.length);
    }
  }
  beginPath() { this._subs = []; this._arcs = 0; this._len = 0; }
  moveTo(x, y) { this._subs.push([[x, y]]); }
  lineTo(x, y) {
    if (!this._subs.length) this.moveTo(x, y);
    const sub = this._subs[this._subs.length - 1];
    const [px, py] = sub[sub.length - 1];
    this._len += Math.hypot(x - px, y - py);
    sub.push([x, y]);
  }
  quadraticCurveTo(_a, _b, x, y) { this.lineTo(x, y); }
  bezierCurveTo(_a, _b, _c, _d, x, y) { this.lineTo(x, y); }
  arc(x, y, r, a0 = 0, a1 = 2 * Math.PI) {
    const sweep = Math.min(Math.abs(a1 - a0), 2 * Math.PI);
    this._arcs += 0.5 * r * r * sweep;
    this._len += r * sweep;
  }
  ellipse(x, y, rx, ry, _rot, a0 = 0, a1 = 2 * Math.PI) {
    const sweep = Math.min(Math.abs(a1 - a0), 2 * Math.PI);
    this._arcs += 0.5 * rx * ry * sweep;
    this._len += 0.5 * (rx + ry) * sweep;
  }
  rect(x, y, w, h) { this.moveTo(x, y); this.lineTo(x + w, y); this.lineTo(x + w, y + h); this.lineTo(x, y + h); }
  roundRect(x, y, w, h) { this.rect(x, y, w, h); }
  closePath() {}
  fill() {
    let area = this._arcs;
    for (const sub of this._subs) {
      let a = 0;
      for (let i = 0; i < sub.length; i++) {
        const [x0, y0] = sub[i], [x1, y1] = sub[(i + 1) % sub.length];
        a += x0 * y1 - x1 * y0;
      }
      area += Math.abs(a) / 2;
    }
    this._paint(this.fillStyle, area);
  }
  stroke() { this._paint(this.strokeStyle, this._len * this.lineWidth); }
  fillRect(x, y, w, h) { this._paint(this.fillStyle, Math.abs(w * h)); }
  strokeRect(x, y, w, h) { this._paint(this.strokeStyle, 2 * (Math.abs(w) + Math.abs(h)) * this.lineWidth); }
  fillText() {}
  measureText(t) { return { width: String(t).length * 8 }; }
  createLinearGradient() { return new Gradient(); }
  createRadialGradient() { return new Gradient(); }
  createPattern() { return null; }
  getImageData(x, y, w, h) { return { width: w, height: h, data: new Uint8ClampedArray(w * h * 4) }; }
  createImageData(w, h) { return { width: w, height: h, data: new Uint8ClampedArray(w * h * 4) }; }
}

export class FakeCanvas {
  constructor() { this.width = 300; this.height = 150; this.paint = new Map(); this.style = {}; }
  getContext() { return this._ctx || (this._ctx = new Context2D(this)); }
  toDataURL() { return ''; }
  addEventListener() {}
}

/** The colour painted over the most area, and the canvas's palette by share of paint. */
export function dominant(canvas) {
  const total = [...canvas.paint.values()].reduce((a, b) => a + b, 0) || 1;
  const palette = [...canvas.paint.entries()].sort((a, b) => b[1] - a[1]).slice(0, 8)
    .map(([c, w]) => ({ colour: c, share: Math.round((w / total) * 1000) / 1000 }));
  const top = palette.length ? palette[0].colour : '#ffffff';
  return { rgb: [1, 3, 5].map((i) => parseInt(top.slice(i, i + 2), 16)), palette };
}
