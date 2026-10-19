// A photograph treated as a shallow 3D scene. The image is split into depth
// (from an optional depth map, else estimated from where things sit in the
// frame and whether they look like sky), then the camera dollies, parallaxes
// and relights it as the page scrolls.

export const photoVertex = /* glsl */ `
attribute vec2 aPos;
varying vec2 vUv;
void main() {
  vUv = aPos * 0.5 + 0.5;
  gl_Position = vec4(aPos, 0.0, 1.0);
}
`;

export const photoFragment = /* glsl */ `
#ifdef GL_FRAGMENT_PRECISION_HIGH
precision highp float;
#else
precision mediump float;
#endif


uniform sampler2D uImage;
uniform sampler2D uDepth;
uniform float uHasDepth;
uniform vec2 uCover;     // scale that maps screen uv to an object-fit: cover crop
uniform vec2 uAnchor;    // object-position of that crop, in uv
uniform vec2 uFocus;     // the dome, in image uv; the dolly pushes toward it
uniform vec2 uSun;       // where the light comes from, in screen uv
uniform vec2 uPointer;   // smoothed, -1..1
uniform float uZoom;     // 1 = matches the <img> underneath exactly
uniform float uLift;     // vertical camera rise from scroll, in uv
uniform float uDusk;     // 0 afternoon, 0.5 golden hour, 1 dusk
uniform float uTime;
uniform float uMotion;   // 0 when the reader prefers reduced motion
uniform float uAspect;   // viewport width / height

varying vec2 vUv;

float hash(vec2 p) {
  p = fract(p * vec2(123.34, 456.21));
  p += dot(p, p + 45.32);
  return fract(p.x * p.y);
}

float noise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), u.x),
             mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x), u.y);
}

float fbm(vec2 p) {
  float v = 0.0;
  float a = 0.5;
  for (int i = 0; i < 5; i++) {
    v += a * noise(p);
    p = p * 2.03 + 11.7;
    a *= 0.5;
  }
  return v;
}

vec2 toImage(vec2 screenUv) {
  vec2 uv = screenUv * uCover + uAnchor * (1.0 - uCover);
  return uFocus + (uv - uFocus) / uZoom;
}

// How sky-like a pixel is. The depth map carries a hand-checked mask in its
// green channel; without one, guess from colour: clearly blue and high up.
float skyAt(vec2 uv) {
  if (uHasDepth > 0.5) return texture2D(uDepth, uv).g;
  vec3 c = texture2D(uImage, uv).rgb;
  return smoothstep(0.06, 0.2, c.b - c.r) * smoothstep(0.35, 0.6, uv.y);
}

float depthAt(vec2 uv) {
  if (uHasDepth > 0.5) return texture2D(uDepth, uv).r; // 1 = near
  float ground = 1.0 - smoothstep(0.0, 0.4, uv.y);     // lawn and steps sit closest
  return mix(0.42, 1.0, ground) * (1.0 - skyAt(uv));
}

void main() {
  vec2 base = toImage(vUv);

  // Parallax: near pixels slide further than far ones. Two refinement steps
  // keep thin edges (columns, the statue) from tearing.
  vec2 shift = (uPointer * vec2(0.010, -0.006) + vec2(0.0, uLift)) * uMotion;
  vec2 uv = base;
  for (int i = 0; i < 2; i++) {
    float d = depthAt(uv);
    uv = base - shift * (d - 0.35);
  }
  uv = clamp(uv, vec2(0.001), vec2(0.999));

  float depth = depthAt(uv);
  // A breath of chromatic fringe toward the edges, like a real lens.
  vec2 fromCenter = vUv - 0.5;
  float edge = dot(fromCenter, fromCenter);
  vec2 ca = fromCenter * edge * 0.006;
  vec3 col;
  col.r = texture2D(uImage, uv + ca).r;
  col.g = texture2D(uImage, uv).g;
  col.b = texture2D(uImage, uv - ca).b;

  float sky = skyAt(uv);
  float lum = dot(col, vec3(0.299, 0.587, 0.114));

  // Cloud shadows crawl across the stone and lawn.
  float t = uTime * uMotion;
  float clouds = fbm(uv * vec2(2.2, 3.2) + vec2(t * 0.012, t * 0.004));
  float shade = smoothstep(0.42, 0.72, clouds);
  col *= 1.0 - shade * 0.13 * (1.0 - sky) * (1.0 - uDusk * 0.7);

  // Light: afternoon -> golden hour -> dusk.
  float golden = smoothstep(0.0, 0.55, uDusk) * (1.0 - smoothstep(0.7, 1.0, uDusk));
  float night = smoothstep(0.45, 1.0, uDusk);
  vec3 warm = vec3(1.18, 0.98, 0.74);
  vec3 shadowBlue = vec3(0.62, 0.70, 0.95);
  vec3 lit = col * mix(vec3(1.0), warm, golden);
  // Shadows go cool as the sun drops, highlights stay warm.
  lit = mix(lit, lit * shadowBlue, night * (1.0 - smoothstep(0.25, 0.75, lum)) * 0.8);
  lit *= mix(1.0, 0.58, night * (1.0 - sky * 0.35));
  // The dusk sky gets its own gradient: ember at the horizon, deep blue overhead.
  vec3 duskSky = mix(vec3(0.98, 0.56, 0.32), vec3(0.16, 0.22, 0.42), smoothstep(0.45, 1.0, uv.y));
  lit = mix(lit, duskSky * (0.55 + lum * 0.7), sky * night * 0.75);
  // Warm lit windows and lanterns at dusk: bright, warm pixels in the building.
  float glowable = smoothstep(0.62, 0.9, lum) * (1.0 - sky) * smoothstep(0.05, 0.0, col.b - col.r);
  lit += vec3(1.0, 0.72, 0.38) * glowable * night * 0.35;

  // Atmospheric perspective: far things pick up the colour of the air.
  vec3 haze = mix(vec3(0.80, 0.86, 0.95), vec3(0.95, 0.62, 0.42), golden);
  haze = mix(haze, vec3(0.28, 0.30, 0.42), night);
  lit = mix(lit, haze, (1.0 - depth) * (1.0 - sky) * 0.12);

  // Sun glow and light shafts radiating from behind the dome.
  vec2 sunDelta = (vUv - uSun) * vec2(uAspect, 1.0);
  float sunDist = length(sunDelta);
  float glow = exp(-sunDist * 3.2) * 0.35 + exp(-sunDist * 14.0) * 0.4;
  float rays = 0.0;
  vec2 stepUv = (vUv - uSun) / 16.0;
  vec2 sUv = vUv;
  for (int i = 0; i < 16; i++) {
    sUv -= stepUv;
    rays += skyAt(clamp(toImage(sUv), 0.001, 0.999)) * (1.0 - float(i) / 16.0);
  }
  rays = rays / 16.0 * exp(-sunDist * 1.6);
  vec3 sunCol = mix(vec3(1.0, 0.93, 0.8), vec3(1.0, 0.62, 0.3), golden + night * 0.5);
  float sunAmt = mix(0.85, 1.25, golden) * (1.0 - night * 0.75);
  lit += sunCol * (glow * 0.6 + rays * 0.45) * sunAmt;

  // Gentle filmic shoulder so the extra light rolls off instead of clipping.
  lit = lit / (1.0 + lit * 0.18) * 1.12;

  // Vignette and grain.
  lit *= 1.0 - edge * mix(0.55, 0.9, night);
  float grain = hash(vUv * 900.0 + fract(t * 7.0)) - 0.5;
  lit += grain * 0.022;

  gl_FragColor = vec4(lit, 1.0);
}
`;
