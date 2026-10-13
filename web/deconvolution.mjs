// Browser-side implementation of Ruifrok–Johnston optical-density unmixing.
// All processing runs locally; no pixel data is transmitted.
export const STAIN_VECTORS = Object.freeze({
  HE: [[0.650, 0.704, 0.286], [0.072, 0.990, 0.105]],
  HDAB: [[0.650, 0.704, 0.286], [0.268, 0.570, 0.776]]
});
export const MAX_PIXELS = 12000000;

function normalized(vector) {
  if (!Array.isArray(vector) || vector.length !== 3 || !vector.every(Number.isFinite)) {
    throw new Error("Each stain vector must contain three finite RGB OD values.");
  }
  const magnitude = Math.hypot(...vector);
  if (!(magnitude > 1e-10)) throw new Error("Stain vectors must have nonzero length.");
  return vector.map(value => value / magnitude);
}

export function buildStainMatrix(vectors) {
  if (!Array.isArray(vectors) || (vectors.length !== 2 && vectors.length !== 3)) {
    throw new Error("Provide two or three stain vectors.");
  }
  const rows = vectors.map(normalized);
  if (rows.length === 2) {
    const [a, b] = rows;
    rows.push(normalized([
      a[1] * b[2] - a[2] * b[1],
      a[2] * b[0] - a[0] * b[2],
      a[0] * b[1] - a[1] * b[0]
    ]));
  }
  invert3(rows);
  return rows;
}

export function invert3(rows) {
  if (!Array.isArray(rows) || rows.length !== 3 || rows.some(row => !Array.isArray(row) || row.length !== 3 || !row.every(Number.isFinite))) {
    throw new Error("Stain matrix must be finite and 3×3.");
  }
  const [[a,b,c],[d,e,f],[g,h,i]] = rows;
  const det = a * (e*i - f*h) - b * (d*i - f*g) + c * (d*h - e*g);
  if (!Number.isFinite(det) || Math.abs(det) < 1e-10) {
    throw new Error("Stain vectors are linearly dependent.");
  }
  return [
    [(e*i-f*h)/det, (c*h-b*i)/det, (b*f-c*e)/det],
    [(f*g-d*i)/det, (a*i-c*g)/det, (c*d-a*f)/det],
    [(d*h-e*g)/det, (b*g-a*h)/det, (a*e-b*d)/det]
  ];
}

function intensity(od) {
  return Math.trunc(Math.max(0, Math.min(255, 255 * Math.pow(10, -od))));
}

export function deconvolvePixels(image, config = {}) {
  const {width, height, data} = image || {};
  if (!Number.isSafeInteger(width) || !Number.isSafeInteger(height) ||
      width <= 0 || height <= 0 || width * height > MAX_PIXELS ||
      !data || data.length !== width * height * 4) {
    throw new Error("Use a valid RGB image of at most 12 megapixels.");
  }
  const preset = config.preset || "HE";
  if (!Object.hasOwn(STAIN_VECTORS, preset)) throw new Error("Unknown stain preset.");
  const mode = config.mode || "pseudocolor";
  if (!["pseudocolor", "grayscale"].includes(mode)) throw new Error("Unknown rendering mode.");
  const threshold = config.threshold ?? 0.15;
  if (!Number.isFinite(threshold) || threshold < 0) throw new Error("Threshold must be a nonnegative finite number.");
  const reference = config.whiteRef ?? null;
  if (reference !== null && (!Array.isArray(reference) || reference.length !== 3 ||
      !reference.every(v => Number.isFinite(v) && v >= 1 && v <= 255))) {
    throw new Error("White reference must have three components between 1 and 255.");
  }
  const matrix = buildStainMatrix(STAIN_VECTORS[preset]);
  const inv = invert3(matrix);
  const names = preset === "HE" ? ["hematoxylin", "eosin", "residual"] : ["hematoxylin", "dab", "residual"];
  const pixels = width * height;
  const channels = names.map(() => new Uint8ClampedArray(pixels * 4));
  const stats = names.map(() => ({sum: 0, min: Infinity, max: -Infinity, positive: 0}));
  for (let p = 0; p < pixels; p++) {
    const j = p * 4;
    const od = [0, 0, 0];
    for (let k = 0; k < 3; k++) {
      const raw = reference ? Math.min(255, data[j+k] * 255 / reference[k]) : data[j+k];
      od[k] = -Math.log10(Math.max(1, Math.min(255, raw)) / 255);
    }
    for (let s = 0; s < 3; s++) {
      const c = od[0] * inv[0][s] + od[1] * inv[1][s] + od[2] * inv[2][s];
      const st = stats[s];
      st.sum += c;
      st.min = Math.min(st.min, c);
      st.max = Math.max(st.max, c);
      if (c > threshold) st.positive++;
      for (let k = 0; k < 3; k++) {
        channels[s][j+k] = intensity(mode === "grayscale" ? c : c * matrix[s][k]);
      }
      channels[s][j+3] = 255;
    }
  }
  return {
    names,
    matrix,
    channels,
    statistics: Object.fromEntries(names.map((name, s) => [name, {
      mean_od: stats[s].sum / pixels,
      max_od: stats[s].max,
      min_od: stats[s].min,
      percent_positive_area: 100 * stats[s].positive / pixels
    }]))
  };
}
