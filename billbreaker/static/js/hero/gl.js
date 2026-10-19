// The handful of raw WebGL calls the photo pass needs: one program, one
// full-screen triangle, and image textures. No 3D engine required.

export function createProgram(gl, vert, frag) {
  const compile = (type, src) => {
    const sh = gl.createShader(type);
    gl.shaderSource(sh, src);
    gl.compileShader(sh);
    if (!gl.getShaderParameter(sh, gl.COMPILE_STATUS)) {
      throw new Error(gl.getShaderInfoLog(sh) ?? "shader compile failed");
    }
    return sh;
  };
  const program = gl.createProgram();
  const vs = compile(gl.VERTEX_SHADER, vert);
  const fs = compile(gl.FRAGMENT_SHADER, frag);
  gl.attachShader(program, vs);
  gl.attachShader(program, fs);
  gl.linkProgram(program);
  gl.deleteShader(vs);
  gl.deleteShader(fs);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
    throw new Error(gl.getProgramInfoLog(program) ?? "program link failed");
  }
  return program;
}

/** A single triangle that covers the viewport, bound to aPos. */
export function fullscreenTriangle(gl, program) {
  const buffer = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
  const loc = gl.getAttribLocation(program, "aPos");
  gl.enableVertexAttribArray(loc);
  gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
  return buffer;
}

export function setUniforms(gl, program, uniforms) {
  for (const name in uniforms) {
    const loc = gl.getUniformLocation(program, name);
    if (!loc) continue;
    const v = uniforms[name];
    if (typeof v === "number") gl.uniform1f(loc, v);
    else if (v.length === 2) gl.uniform2f(loc, v[0], v[1]);
    else if (v.length === 3) gl.uniform3f(loc, v[0], v[1], v[2]);
  }
}

export function loadImage(src) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.decoding = "async";
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error(`could not load ${src}`));
    img.src = src;
  });
}

const isPow2 = (n) => (n & (n - 1)) === 0;

/** Uploads an image, flipped so uv (0,0) is bottom-left, with mipmaps where WebGL allows. */
export function imageTexture(gl, img) {
  const tex = gl.createTexture();
  gl.bindTexture(gl.TEXTURE_2D, tex);
  gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, true);
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, img);
  const webgl2 = typeof WebGL2RenderingContext !== "undefined" && gl instanceof WebGL2RenderingContext;
  const mips = webgl2 || (isPow2(img.width) && isPow2(img.height));
  if (mips) gl.generateMipmap(gl.TEXTURE_2D);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, mips ? gl.LINEAR_MIPMAP_LINEAR : gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
  const aniso = gl.getExtension("EXT_texture_filter_anisotropic");
  if (aniso && mips) {
    gl.texParameterf(
      gl.TEXTURE_2D,
      aniso.TEXTURE_MAX_ANISOTROPY_EXT,
      Math.min(8, gl.getParameter(aniso.MAX_TEXTURE_MAX_ANISOTROPY_EXT)),
    );
  }
  return tex;
}
