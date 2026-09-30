"use strict";

const $ = id => document.getElementById(id);
const radians = Math.PI / 180;
const degrees = 180 / Math.PI;
const clamp = (value, low, high) => Math.max(low, Math.min(high, value));
const escapeHtml = value => String(value).replace(/[&<>"']/g, char => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
})[char]);

const vertexShader = `attribute vec2 aPosition;
void main() { gl_Position = vec4(aPosition, 0.0, 1.0); }`;
const fragmentShader = `precision highp float;
uniform sampler2D uTexture;
uniform sampler2D uStrip;
uniform sampler2D uHeight;
uniform sampler2D uOverlap;
uniform vec2 uCanvas;
uniform vec2 uCenter;
uniform float uRadius;
uniform float uStripMode;
uniform float uFocusStrip;
uniform float uOverlapMode;
uniform vec4 uStripBounds;
uniform vec4 uStripTop;
uniform vec4 uStripBottom;
const float PI = 3.141592653589793;
void main() {
  vec2 point = (gl_FragCoord.xy - uCanvas * 0.5) / uRadius;
  float distanceSquared = dot(point, point);
  if (distanceSquared > 1.0) discard;
  float depth = sqrt(1.0 - distanceSquared);
  float longitude = uCenter.x, latitude = uCenter.y;
  vec3 east = vec3(-sin(longitude), cos(longitude), 0.0);
  vec3 north = vec3(-sin(latitude)*cos(longitude), -sin(latitude)*sin(longitude), cos(latitude));
  vec3 front = vec3(cos(latitude)*cos(longitude), cos(latitude)*sin(longitude), sin(latitude));
  vec3 surface = point.x*east + point.y*north + depth*front;
  vec2 uv = vec2(fract(atan(surface.y, surface.x)/(2.0*PI)+0.5), asin(clamp(surface.z,-1.0,1.0))/PI+0.5);
  vec3 moon = texture2D(uTexture, uv).rgb;
  if (uFocusStrip > 0.5) moon *= 0.42;
  if (uStripMode > 0.5 && surface.z < 0.0) {
    float latitudeDegrees = asin(clamp(surface.z,-1.0,1.0));
    float polarRadius = 3474800.0 * tan(PI*0.25 + latitudeDegrees*0.5);
    vec2 polar = polarRadius * vec2(surface.y, surface.x) / max(length(surface.xy), 0.00001);
    vec2 stripUV;
    if (uStripMode > 1.5) {
      stripUV = vec2((polar.x-uStripBounds.x)/(uStripBounds.z-uStripBounds.x),
                     (uStripBounds.w-polar.y)/(uStripBounds.w-uStripBounds.y));
    } else {
      vec2 topLeft = uStripTop.xy;
      vec2 along = uStripTop.zw-topLeft;
      vec2 down = uStripBottom.xy-topLeft;
      vec2 offset = polar-topLeft;
      float determinant = along.x*down.y-along.y*down.x;
      stripUV = vec2((offset.x*down.y-offset.y*down.x)/determinant,
                     (along.x*offset.y-along.y*offset.x)/determinant);
    }
    if (stripUV.x >= 0.0 && stripUV.x <= 1.0 && stripUV.y >= 0.0 && stripUV.y <= 1.0) {
      vec4 strip = texture2D(uStrip, vec2(stripUV.x,1.0-stripUV.y));
      if (uStripMode < 1.5 || strip.a > 0.5) moon = strip.rgb;
    }
  }
  vec3 eastSurface = normalize(vec3(-surface.y, surface.x, 0.0) + vec3(0.000001));
  vec3 northSurface = normalize(cross(surface, eastSurface));
  vec2 heightStep = vec2(1.0/1024.0, 1.0/512.0);
  float eastSlope = (texture2D(uHeight, uv+vec2(heightStep.x,0.0)).r -
                     texture2D(uHeight, uv-vec2(heightStep.x,0.0)).r) *
                    (20000.0/(2.0*2.0*PI*1737400.0/1024.0*max(length(surface.xy),0.08)));
  float northSlope = (texture2D(uHeight, uv+vec2(0.0,heightStep.y)).r -
                      texture2D(uHeight, uv-vec2(0.0,heightStep.y)).r) *
                     (20000.0/(2.0*PI*1737400.0/512.0));
  float relief = 1.0-smoothstep(600.0,2400.0,uRadius);
  vec3 terrainNormal = normalize(surface-relief*(eastSlope*eastSurface+northSlope*northSurface));
  vec3 normalView = vec3(dot(terrainNormal,east),dot(terrainNormal,north),dot(terrainNormal,front));
  float sunlight = max(dot(normalView, normalize(vec3(-0.38,0.53,0.78))), 0.0);
  float shade = (0.16 + 0.86*sunlight) * (1.0 - 0.28*smoothstep(0.72,1.0,distanceSquared));
  moon *= shade;
  if (uOverlapMode > 0.5) {
    float coverage = texture2D(uOverlap, vec2(fract(uv.x + 0.5), uv.y)).r;
    if (coverage > 6.5/255.0 && coverage < 7.5/255.0)
      moon = mix(moon, vec3(1.0, 0.75, 0.17), 0.82);
  }
  gl_FragColor = vec4(moon, 1.0);
}`;

function compile(gl, type, source) {
  const shader = gl.createShader(type);
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) throw Error(gl.getShaderInfoLog(shader));
  return shader;
}

function makeRenderer(canvas) {
  const gl = canvas.getContext("webgl", {alpha: true});
  if (!gl) throw Error("WebGL is unavailable in this browser");
  const program = gl.createProgram();
  gl.attachShader(program, compile(gl, gl.VERTEX_SHADER, vertexShader));
  gl.attachShader(program, compile(gl, gl.FRAGMENT_SHADER, fragmentShader));
  gl.linkProgram(program);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw Error(gl.getProgramInfoLog(program));
  gl.useProgram(program);
  const vertices = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, vertices);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1, 1,-1, -1,1, -1,1, 1,-1, 1,1]), gl.STATIC_DRAW);
  const attribute = gl.getAttribLocation(program, "aPosition");
  gl.enableVertexAttribArray(attribute);
  gl.vertexAttribPointer(attribute, 2, gl.FLOAT, false, 0, 0);
  const uniforms = Object.fromEntries(["uCanvas", "uCenter", "uRadius", "uTexture", "uStrip", "uHeight", "uOverlap", "uStripMode", "uFocusStrip", "uOverlapMode", "uStripBounds", "uStripTop", "uStripBottom"].map(name => [name, gl.getUniformLocation(program, name)]));
  const texture = gl.createTexture();
  gl.activeTexture(gl.TEXTURE0);
  gl.bindTexture(gl.TEXTURE_2D, texture);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.REPEAT);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
  gl.uniform1i(uniforms.uTexture, 0);
  const stripTexture = gl.createTexture();
  gl.activeTexture(gl.TEXTURE1);
  gl.bindTexture(gl.TEXTURE_2D, stripTexture);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGB, 1, 1, 0, gl.RGB, gl.UNSIGNED_BYTE, new Uint8Array([80,80,80]));
  gl.uniform1i(uniforms.uStrip, 1);
  const heightTexture = gl.createTexture();
  gl.activeTexture(gl.TEXTURE2);
  gl.bindTexture(gl.TEXTURE_2D, heightTexture);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.REPEAT);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGB, 1, 1, 0, gl.RGB, gl.UNSIGNED_BYTE, new Uint8Array([128,128,128]));
  gl.uniform1i(uniforms.uHeight, 2);
  const heightImage = new Image();
  heightImage.onload = () => {
    gl.activeTexture(gl.TEXTURE2);
    gl.bindTexture(gl.TEXTURE_2D, heightTexture);
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, true);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGB, gl.RGB, gl.UNSIGNED_BYTE, heightImage);
  };
  heightImage.onerror = () => showError("The offline lunar elevation map could not be loaded.");
  heightImage.src = "/science-evidence/globe-assets/nasa_lola_height_1k.jpg";
  const overlapTexture = gl.createTexture();
  gl.activeTexture(gl.TEXTURE3);
  gl.bindTexture(gl.TEXTURE_2D, overlapTexture);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.REPEAT);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, 1, 1, 0, gl.RGBA, gl.UNSIGNED_BYTE, new Uint8Array([0,0,0,255]));
  gl.uniform1i(uniforms.uOverlap, 3);
  const overlapImage = new Image();
  overlapImage.onload = () => {
    gl.activeTexture(gl.TEXTURE3);
    gl.bindTexture(gl.TEXTURE_2D, overlapTexture);
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, true);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, overlapImage);
  };
  overlapImage.onerror = () => showError("The saved global overlap map could not be loaded.");
  overlapImage.src = "/science-evidence/globe-assets/global-triples-validated.png";
  let ready = false;
  let activeStrip = null, request = 0;
  const image = new Image();
  image.onload = () => {
    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, texture);
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, true);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGB, gl.RGB, gl.UNSIGNED_BYTE, image);
    ready = true;
  };
  image.onerror = () => showError("The offline lunar backdrop could not be loaded.");
  image.src = "/science-evidence/globe-assets/nasa_lroc_color_2k.jpg";
  return {
    setStrip(product) {
      const id = ++request;
      activeStrip = null;
      if (!product || !product.image_url) return;
      const stripImage = new Image();
      stripImage.onload = () => {
        if (id !== request) return;
        gl.activeTexture(gl.TEXTURE1);
        gl.bindTexture(gl.TEXTURE_2D, stripTexture);
        gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, true);
        gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, stripImage);
        activeStrip = product;
      };
      stripImage.onerror = () => { if (id === request) showError(`Real image for ${product.product_id} could not be loaded.`); };
      stripImage.src = product.image_url;
    },
    resize(width, height) { gl.viewport(0, 0, width, height); },
    draw(width, height, longitude, latitude, radius, overlapMode, focusStrip) {
      gl.clearColor(0, 0, 0, 0);
      gl.clear(gl.COLOR_BUFFER_BIT);
      if (!ready) return;
      gl.uniform2f(uniforms.uCanvas, width, height);
      gl.uniform2f(uniforms.uCenter, longitude*radians, latitude*radians);
      gl.uniform1f(uniforms.uRadius, radius);
      gl.uniform1f(uniforms.uOverlapMode, overlapMode ? 1 : 0);
      gl.uniform1f(uniforms.uFocusStrip, focusStrip && activeStrip ? 1 : 0);
      gl.uniform1f(uniforms.uStripMode, activeStrip ? (activeStrip.image_mode === "GEOREFERENCED_ORTHO" ? 2 : 1) : 0);
      if (activeStrip) {
        const quad = activeStrip.quad_polar_m;
        gl.uniform4fv(uniforms.uStripBounds, activeStrip.ortho_bounds_m || [0,0,1,1]);
        gl.uniform4fv(uniforms.uStripTop, [...quad[0], ...quad[1]]);
        gl.uniform4fv(uniforms.uStripBottom, [...quad[2], ...quad[3]]);
      }
      gl.drawArrays(gl.TRIANGLES, 0, 6);
    }
  };
}

function showError(message) {
  $("error").textContent = message;
  $("error").hidden = false;
}

async function start() {
  const response = await fetch("/science-evidence/globe-assets/globe-footprints.json");
  if (!response.ok) throw Error("Saved catalogue geometry is unavailable");
  const catalogue = await response.json();
  const products = catalogue.products;
  const auditedOhrc="ch2_ohr_nrp_20241117T2033118394_d_img_d18";
  const auditedTmc="ch2_tmc_ndn_20231101T0125121377_d_oth_d18";
  const rejectedOhrc="ch2_ohr_nrp_20200827T0030107497_d_img_d18";
  const overlapResponse = await fetch("/science-evidence/globe-assets/overlap-regions.json");
  if (!overlapResponse.ok) throw Error("Saved triple-overlap geometry is unavailable");
  const overlapCatalogue = await overlapResponse.json();
  const tripleRegions = overlapCatalogue.regions.filter(region => region.kind === "CATALOGUE_TRIPLE" && region.product_ids.length === 3);
  const maskImage = await new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(Error("Saved global triple-overlap map is unavailable"));
    image.src = "/science-evidence/globe-assets/global-triples-validated.png";
  });
  const [pointIndexResponse, clustersResponse] = await Promise.all([
    fetch("/science-evidence/globe-assets/global-triple-product-index.json"),
    fetch("/science-evidence/globe-assets/global-triple-display-clusters.json"),
  ]);
  if (!pointIndexResponse.ok || !clustersResponse.ok) throw Error("Validated global triple catalogue is unavailable");
  const pointIndex = await pointIndexResponse.json();
  const clusters = (await clustersResponse.json()).clusters;
  const auditedCluster=clusters.find(cluster=>cluster.product_ids.includes(auditedOhrc)&&cluster.product_ids.includes(auditedTmc));
  const productsAtCell = new Map(pointIndex.entries.map(([cell, ...indices]) => [cell, indices]));
  const maskCanvas = document.createElement("canvas");
  maskCanvas.width = maskImage.naturalWidth;
  maskCanvas.height = maskImage.naturalHeight;
  const maskContext = maskCanvas.getContext("2d", {willReadFrequently: true});
  maskContext.drawImage(maskImage, 0, 0);
  const maskPixels = maskContext.getImageData(0, 0, maskCanvas.width, maskCanvas.height).data;
  function isGlobalTriple([longitude, latitude]) {
    const col = Math.floor((longitude % 360) / 360 * maskCanvas.width) % maskCanvas.width;
    const row = clamp(Math.floor((90 - latitude) / 180 * maskCanvas.height), 0, maskCanvas.height - 1);
    return maskPixels[4 * (row * maskCanvas.width + col)] === 7;
  }
  for (const region of tripleRegions) {
    const vertices = region.rings_lon_lat.flat();
    const mean = vertices.reduce((sum,[lon,lat]) => {
      const phi=lat*radians,lambda=lon*radians;
      sum[0]+=Math.cos(phi)*Math.cos(lambda);
      sum[1]+=Math.cos(phi)*Math.sin(lambda);
      sum[2]+=Math.sin(phi);
      return sum;
    },[0,0,0]);
    region.center_lon_lat=[((Math.atan2(mean[1],mean[0])*degrees)%360+360)%360,
      Math.atan2(mean[2],Math.hypot(mean[0],mean[1]))*degrees];
  }
  for (const product of products) {
    const step = Math.max(1,Math.ceil(product.ring_lon_lat.length/80));
    product.pickRing = product.ring_lon_lat.filter((_,index) => index%step===0);
  }
  const wrap = $("globeWrap"), moon = $("moon"), overlay = $("footprints");
  const context = overlay.getContext("2d"), renderer = makeRenderer(moon);
  const state = {longitude:10, latitude:-25, radius:0, targetLongitude:10, targetLatitude:-25,
    targetRadius:0, pendingZoom:0, width:0, height:0, pixelRatio:1, visible:new Set(), selected:null,
    spinning:true, drag:null, tripleMode:false, activeTriple:null, tripleReturn:null, overlapReturn:null};
  let drapeChoices=[];
  function showGlobeImage(product) {
    renderer.setStrip(product);
    const note=$("globeImageNote");
    note.hidden=!product;
    if (!product) return;
    const approximate=product.image_mode!=="GEOREFERENCED_ORTHO";
    note.innerHTML=`<b>REAL ${escapeHtml(product.sensor)} ${approximate?"BROWSE":"ORTHO"} ON MOON</b><small>${escapeHtml(product.product_id)}</small><small>${approximate?"Approximate catalogue-corner placement · visual only":"Georeferenced ortho display · 5 m nominal"}</small>${drapeChoices.length>1?`<div class="globe-drape-options">${drapeChoices.map(choice=>`<button type="button" data-drape="${escapeHtml(choice.product_id)}" aria-pressed="${choice===product}">${escapeHtml(choice.sensor)} ${choice.image_mode==="GEOREFERENCED_ORTHO"?"ortho":"browse"}</button>`).join("")}</div>`:""}`;
  }
  $("globeImageNote").onclick=event=>{
    const button=event.target.closest("button[data-drape]");
    if (button) showGlobeImage(drapeChoices.find(choice=>choice.product_id===button.dataset.drape));
  };

  const sensors = ["OHRC", "TMC-2", "IIRS"];
  const featured = new Map(sensors.map(sensor => [sensor, products.find(product => product.sensor === sensor && product.status === "LOCAL ROI ONLY") || products.find(product => product.sensor === sensor && product.featured)]));
  const northOhrc = products.find(product => product.sensor === "OHRC" && product.source_layer.endsWith("_np") && product.product_id.endsWith("_d18"));
  const byId = new Map(products.map(product => [product.product_id, product]));
  const rejectedProduct=byId.get(rejectedOhrc);
  // The saved catalogue rings place this OHRC footprint inside the TMC-2
  // footprint. This is an audited two-sensor case, never a triple claim.
  const rejectedPair=rejectedProduct ? {
    id:"REALPAIR001_REJECTED_PAIR",kind:"AUDITED_PAIR_REJECTED",
    product_ids:[rejectedOhrc,auditedTmc],
    center_lon_lat:rejectedProduct.center_lon_lat,
    rings_lon_lat:[rejectedProduct.ring_lon_lat],globalMask:false,
  } : null;
  function globalTripleAt(location) {
    if (!location || !isGlobalTriple(location)) return null;
    const col = Math.floor((location[0] % 360) / 360 * maskCanvas.width) % maskCanvas.width;
    const row = clamp(Math.floor((90 - location[1]) / 180 * maskCanvas.height), 0, maskCanvas.height - 1);
    const indices = productsAtCell.get(row * maskCanvas.width + col);
    if (!indices) return null;
    return {
      id: `GLOBAL_${location[0].toFixed(3)}_${location[1].toFixed(3)}`,
      kind: "CATALOGUE_TRIPLE_GLOBAL",
      product_ids: indices.map(index => products[index].product_id),
      center_lon_lat: location,
      rings_lon_lat: [],
      globalMask: true,
    };
  }
  $("sensorButtons").innerHTML = sensors.map(sensor => {
    const entries = products.filter(product => product.sensor === sensor);
    const product = featured.get(sensor) || entries[0];
    return `<button class="sensor" type="button" data-sensor="${escapeHtml(sensor)}" aria-pressed="false" style="--color:${product.color}"><span class="sensor-mark"></span><span class="sensor-copy"><strong>${escapeHtml(sensor)}</strong><small>${entries.length} catalogue strips · ${product.resolution_m} m/px</small></span><span class="sensor-state">SHOW</span></button>`;
  }).join("");
  const buttons = [...document.querySelectorAll(".sensor")];
  function renderList() {
    const query = $("productSearch").value.trim().toLowerCase();
    $("productList").hidden = !query;
    if (!query) { $("productList").innerHTML = ""; $("listSummary").textContent = ""; return; }
    const matches = products.filter(product => product.product_id.toLowerCase().includes(query));
    const priority = product => product.status === "LOCAL ROI ONLY" ? 2 : product.image_url ? 1 : 0;
    matches.sort((a,b) => priority(b)-priority(a));
    $("productList").innerHTML = matches.slice(0, 30).map(product => `<button type="button" data-id="${escapeHtml(product.product_id)}" class="product-row${state.selected===product.product_id ? " selected" : ""}" style="--color:${product.color}"><span class="product-dot"></span><span class="product-row-copy"><strong>${escapeHtml(product.product_id)}</strong><small>${escapeHtml(product.sensor)} · ${product.image_url ? "LOCAL IMAGE" : "FOOTPRINT ONLY"}</small></span></button>`).join("") || '<p class="no-products">No saved product IDs match this search.</p>';
    $("listSummary").textContent = matches.length>30 ? `Showing 30 of ${matches.length} matches; type more to narrow` : "";
  }
  function updateButtons() {
    for (const button of buttons) {
      const active = state.visible.has(button.dataset.sensor);
      button.setAttribute("aria-pressed", String(active));
      button.querySelector(".sensor-state").textContent = active ? "ON" : "SHOW";
    }
    renderList();
  }
  $("productSearch").addEventListener("input", renderList);
  $("productList").addEventListener("click", event => {
    const button = event.target.closest("button[data-id]");
    if (button) { focus(byId.get(button.dataset.id)); $("productSearch").value=""; renderList(); }
  });
  renderList();
  function baseRadius() { return Math.min(state.width, state.height) * 0.44; }
  function resize() {
    const box = wrap.getBoundingClientRect();
    const previousBase = state.width && state.height ? baseRadius() : 0;
    state.width = box.width;
    state.height = box.height;
    if (previousBase) {
      const scale = baseRadius() / previousBase;
      state.radius *= scale;
      state.targetRadius *= scale;
      if (state.pendingZoom) state.pendingZoom *= scale;
    }
    state.pixelRatio = Math.min(devicePixelRatio || 1, 2);
    for (const canvas of [moon, overlay]) {
      canvas.width = Math.round(box.width * state.pixelRatio);
      canvas.height = Math.round(box.height * state.pixelRatio);
    }
    context.setTransform(state.pixelRatio, 0, 0, state.pixelRatio, 0, 0);
    renderer.resize(moon.width, moon.height);
    if (!previousBase) state.radius = state.targetRadius = baseRadius();
  }
  new ResizeObserver(resize).observe(wrap);
  resize();

  function project(longitude, latitude) {
    const delta = (longitude-state.longitude)*radians;
    const phi = latitude*radians, center = state.latitude*radians;
    const east = Math.cos(phi)*Math.sin(delta);
    const north = Math.sin(phi)*Math.cos(center)-Math.cos(phi)*Math.sin(center)*Math.cos(delta);
    const depth = Math.sin(phi)*Math.sin(center)+Math.cos(phi)*Math.cos(center)*Math.cos(delta);
    return {x:state.width/2+state.radius*east, y:state.height/2-state.radius*north, depth};
  }
  function geographicPoint(x, y) {
    const east = (x-state.width/2)/state.radius;
    const north = (state.height/2-y)/state.radius;
    if (east*east+north*north > 1) return null;
    const depth = Math.sqrt(1-east*east-north*north);
    const phi = state.latitude*radians, lambda = state.longitude*radians;
    const wx = -east*Math.sin(lambda)-north*Math.sin(phi)*Math.cos(lambda)+depth*Math.cos(phi)*Math.cos(lambda);
    const wy = east*Math.cos(lambda)-north*Math.sin(phi)*Math.sin(lambda)+depth*Math.cos(phi)*Math.sin(lambda);
    const wz = north*Math.cos(phi)+depth*Math.sin(phi);
    return [((Math.atan2(wy,wx)*degrees)%360+360)%360, Math.asin(clamp(wz,-1,1))*degrees];
  }
  function pointInPolygon(point, ring) {
    const [x,y] = point;
    const near = longitude => x + ((longitude-x+540)%360)-180;
    let inside = false;
    for (let i=0,j=ring.length-1;i<ring.length;j=i++) {
      const [rawI,yi]=ring[i], [rawJ,yj]=ring[j];
      const xi=near(rawI),xj=near(rawJ);
      if ((yi>y)!==(yj>y) && x<(xj-xi)*(y-yi)/(yj-yi)+xi) inside=!inside;
    }
    return inside;
  }
  function sameProducts(left, right) {
    return left.length===right.length && left.every(id => right.includes(id));
  }
  function resolveTripleGeometry(region) {
    if (!region?.globalMask && region?.rings_lon_lat?.length) return region;
    const exact=tripleRegions.filter(candidate => sameProducts(candidate.product_ids,region.product_ids));
    const candidates=exact.length ? exact : tripleRegions.filter(candidate =>
      candidate.rings_lon_lat.some(ring => pointInPolygon(region.center_lon_lat,ring)));
    if (!candidates.length) return region;
    return candidates.reduce((nearest,candidate) => {
      const distance=item => {
        const longitudeDelta=((((item.center_lon_lat[0]-region.center_lon_lat[0])+540)%360)-180)*Math.cos(region.center_lon_lat[1]*radians);
        const latitudeDelta=item.center_lon_lat[1]-region.center_lon_lat[1];
        return longitudeDelta*longitudeDelta+latitudeDelta*latitudeDelta;
      };
      return distance(candidate)<distance(nearest) ? candidate : nearest;
    });
  }
  function pick(x, y) {
    if (state.tripleMode) return null;
    const visible = products.filter(product => (state.visible.has(product.sensor) || product.product_id === state.selected) &&
      (!state.selected || product.product_id === state.selected) && project(...product.center_lon_lat).depth > -0.15);
    for (const product of visible) {
      const marker = project(...product.center_lon_lat);
      if (marker.depth>0 && Math.hypot(x-marker.x,y-marker.y)<16) return product;
    }
    const location = geographicPoint(x,y);
    if (!location) return null;
    return visible.sort((a,b) => a.footprint_area_m2-b.footprint_area_m2)
      .find(product => pointInPolygon(location,product.pickRing)) || null;
  }
  function clearDetails() {
    drapeChoices=[];
    renderer.setStrip(null);
    $("globeImageNote").hidden=true;
    $("hoverTag").hidden=true;
    $("zoomOut").hidden=true;
    $("selection").hidden=true;
    $("globeHint").textContent="DRAG TO ROTATE · SCROLL TO ZOOM";
    renderList();
  }
  function setTripleMode(enabled) {
    if (enabled === state.tripleMode) return;
    closeEvidence();
    const returnView=state.overlapReturn;
    if (enabled) {
      state.overlapReturn={longitude:state.longitude,latitude:state.latitude,radius:baseRadius()};
    }
    state.tripleMode=enabled;
    state.activeTriple=null;
    syncVerifyButton();
    state.tripleReturn=null;
    state.visible.clear();
    state.selected=null;
    state.pendingZoom=0;
    clearDetails();
    if (enabled) {
      state.targetLongitude=25;
      state.targetLatitude=-65;
      state.targetRadius=baseRadius();
      $("globeHint").textContent=`${clusters.length} TRIPLE REGIONS + 1 AUDITED PAIR · CLICK TO INSPECT`;
    } else {
      state.targetLongitude=returnView?.longitude ?? 10;
      state.targetLatitude=returnView?.latitude ?? -25;
      state.targetRadius=returnView?.radius ?? baseRadius();
      state.overlapReturn=null;
      renderer.setStrip(null);
      $("globeImageNote").hidden=true;
    }
    $("tripleToggle").setAttribute("aria-pressed",String(enabled));
    $("tripleToggle").innerHTML=enabled ? "× &nbsp; Hide overlaps" : "◎ &nbsp; Triple overlap";
    updateButtons();
  }
  function zoomOut() {
    if (state.tripleMode && state.activeTriple) {
      closeEvidence();
      state.activeTriple=null;
      syncVerifyButton();
      state.pendingZoom=0;
      if (state.tripleReturn) {
        state.targetLongitude=state.tripleReturn.longitude;
        state.targetLatitude=state.tripleReturn.latitude;
        state.targetRadius=baseRadius();
      }
      state.tripleReturn=null;
      drapeChoices=[];
      renderer.setStrip(null);
      $("globeImageNote").hidden=true;
      $("zoomOut").hidden=true;
      $("globeHint").textContent=`${clusters.length} TRIPLE REGIONS + 1 AUDITED PAIR · CLICK A MARKER`;
      return;
    }
    if (!state.selected) return;
    state.selected=null;
    state.pendingZoom=0;
    state.targetRadius=baseRadius();
    clearDetails();
  }
  // Fit every boundary vertex inside the viewport with a visible margin.
  // The same framing rule applies to all three sensors, regardless of strip size.
  function zoomRadius(product) {
    const [longitude, latitude] = viewCenter(product);
    const center = latitude*radians;
    const maxAngle = Math.max(...product.ring_lon_lat.map(([lon,lat]) => Math.acos(clamp(
      Math.sin(center)*Math.sin(lat*radians) + Math.cos(center)*Math.cos(lat*radians)*Math.cos((lon-longitude)*radians), -1, 1))));
    return baseRadius()*.93/Math.max(Math.sin(Math.min(maxAngle,Math.PI/2)), .005);
  }
  function tripleZoomRadius(region) {
    if (region.globalMask) return baseRadius() * 5;
    const [longitude,latitude]=region.center_lon_lat;
    const center=latitude*radians;
    const maxAngle=Math.max(...region.rings_lon_lat.flat().map(([lon,lat]) => Math.acos(clamp(
      Math.sin(center)*Math.sin(lat*radians)+Math.cos(center)*Math.cos(lat*radians)*Math.cos((lon-longitude)*radians),-1,1))));
    return Math.min(100000,baseRadius()*.88/Math.max(Math.sin(Math.min(maxAngle,Math.PI/2)),.00001));
  }
  function viewCenter(product) {
    // Median opaque pixel of the saved georeferenced TMC-2 ortho cutout,
    // converted from its polar-stereographic bounds. This is a camera target,
    // not a change to the footprint or registration geometry.
    if (product.product_id === "ch2_tmc_ndn_20231101T0125121377_d_oth_d18") return [20.912583, -71.229078];
    return product.center_lon_lat;
  }
  function focus(product) {
    if (!product) return;
    closeEvidence();
    $("globeImageNote").hidden=true;
    if (state.tripleMode) setTripleMode(false);
    if (state.selected===product.product_id) {zoomOut();return;}
    state.selected=product.product_id;
    [state.targetLongitude,state.targetLatitude]=viewCenter(product);
    state.targetRadius=baseRadius();
    state.pendingZoom=zoomRadius(product);
    renderer.setStrip(product);
    $("zoomOut").hidden=false;
    $("globeHint").textContent="CLICK STRIP TO ZOOM OUT";
    $("selection").style.setProperty("--color",product.color);
    $("selection").textContent=`${product.sensor} · ${product.product_id} · ${product.image_url ? "LOCAL IMAGE" : "FOOTPRINT ONLY"}`;
    const detail = document.createElement("small");
    detail.textContent=product.sensor === "OHRC"
      ? `${product.acquisition_utc.slice(0,10)} · nominal ${product.resolution_m} m/px · ${product.image_url ? "real browse display" : "catalogue footprint only"}`
      : `${Math.round(product.footprint_area_m2/1e6).toLocaleString()} km² catalogue footprint · nominal ${product.resolution_m} m/px`;
    $("selection").append(detail);
    $("selection").hidden=false;
    updateButtons();
  }
  function drawFootprints() {
    // In triple-overlap inspection the evidence is the common intersection.
    // Drawing three full catalogue swaths at high zoom creates enormous paths
    // outside the canvas and makes region changes appear to tear or freeze.
    if (state.tripleMode) return;
    const visible = state.tripleMode
      ? (state.activeTriple ? state.activeTriple.product_ids.map(id => byId.get(id)) : [])
      : products.filter(item => state.visible.has(item.sensor) || item.product_id === state.selected);
    visible.sort((a,b) => Number(a.product_id===state.selected)-Number(b.product_id===state.selected));
    for (const product of visible) {
      const selected = state.selected===product.product_id;
      if (state.selected && !selected) continue;
      const center = project(...product.center_lon_lat);
      if (center.depth < -0.15 && !selected) continue;
      const stride = selected ? 1 : Math.max(1,Math.ceil(product.ring_lon_lat.length/48));
      const ring = selected ? product.ring_lon_lat : product.ring_lon_lat.filter((_,index) => index%stride===0);
      const points = ring.map(pair => project(...pair));
      context.beginPath();
      let started=false;
      for (const point of points) {
        if (point.depth>0) { started ? context.lineTo(point.x,point.y) : context.moveTo(point.x,point.y); started=true; }
        else started=false;
      }
      context.strokeStyle=product.color;
      context.lineWidth=selected?3:1.2;
      context.globalAlpha=selected?1:.32;
      context.shadowColor=product.color;
      context.shadowBlur=selected?14:0;
      context.stroke();
      context.globalAlpha=1;
      context.shadowBlur=0;
      if (!selected && !state.tripleMode && !product.featured && product !== northOhrc) continue;
      const marker=center;
      if (marker.depth<=0) continue;
      context.beginPath();context.arc(marker.x,marker.y,selected?8:6,0,2*Math.PI);
      context.fillStyle=product.color;context.fill();
      context.beginPath();context.arc(marker.x,marker.y,selected?16:13,0,2*Math.PI);
      context.strokeStyle=product.color;context.lineWidth=1.5;context.stroke();
      context.fillStyle="#f3f6f2";context.font="600 12px system-ui";
      context.fillText(product.sensor,marker.x+19,marker.y+4);
    }
  }
  function drawTripleRegions() {
    if (!state.tripleMode) return;
    if (!state.activeTriple) {
      for (const cluster of clusters) {
        const marker=project(...cluster.center_lon_lat);
        if (marker.depth<=0) continue;
        const audited=cluster.product_ids.includes(auditedOhrc)&&cluster.product_ids.includes(auditedTmc);
        const color=audited?"#6cf1ad":"#ffe08a";
        context.beginPath();context.arc(marker.x,marker.y,audited?7:5,0,2*Math.PI);
        context.fillStyle=color;context.fill();
        context.beginPath();context.arc(marker.x,marker.y,audited?12:9,0,2*Math.PI);
        context.strokeStyle=color;context.lineWidth=audited?2:1.5;context.stroke();
        if(audited){context.font="700 10px ui-monospace,monospace";context.fillStyle="#baffd9";context.fillText("AUDITED OHRC/TMC",marker.x-24,marker.y-18)}
      }
      if (rejectedPair) {
        const marker=project(...rejectedPair.center_lon_lat);
        if(marker.depth>0){
          context.beginPath();context.arc(marker.x,marker.y,7,0,2*Math.PI);
          context.fillStyle="#ff8e85";context.fill();
          context.beginPath();context.arc(marker.x,marker.y,13,0,2*Math.PI);
          context.strokeStyle="#ff8e85";context.lineWidth=2;context.stroke();
          context.font="700 10px ui-monospace,monospace";
          context.fillStyle="#ffd1ca";
          context.fillText("REJECTED OHRC/TMC PAIR",marker.x+17,marker.y-9);
        }
      }
      return;
    }
    const regions=[state.activeTriple];
    for (const region of regions) {
      const marker=project(...region.center_lon_lat);
      if (marker.depth<=0) continue;
      const active=state.activeTriple===region;
      for (const ring of region.rings_lon_lat) {
        const points=ring.map(pair => project(...pair));
        if (points.some(point => point.depth<=0)) continue;
        context.beginPath();
        points.forEach((point,index) => index ? context.lineTo(point.x,point.y) : context.moveTo(point.x,point.y));
        context.closePath();
        const rejected=region.kind==="AUDITED_PAIR_REJECTED";
        context.fillStyle=rejected ? "#eb68612b" : active ? "#f4d56c22" : "#f4d56c80";
        context.strokeStyle=rejected ? "#ff9b92" : "#ffe58b";
        context.lineWidth=active ? 2.5 : 1;
        context.fill();context.stroke();
      }
      context.beginPath();context.arc(marker.x,marker.y,active?7:3.5,0,2*Math.PI);
      context.fillStyle=region.kind==="AUDITED_PAIR_REJECTED"?"#ffafa4":active?"#fff2bd":"#f4d56c";context.fill();
    }
  }
  function pickTriple(x,y) {
    if (state.activeTriple) {
      const marker=project(...state.activeTriple.center_lon_lat);
      if (marker.depth>0 && Math.hypot(x-marker.x,y-marker.y)<18) return state.activeTriple;
      const location=geographicPoint(x,y);
      if (location) {
        const activeProducts=(state.activeTriple.kind==="AUDITED_PAIR_REJECTED" ? [rejectedOhrc] : state.activeTriple.product_ids).map(id => byId.get(id)).filter(Boolean);
        if (activeProducts.some(product => pointInPolygon(location,product.ring_lon_lat))) return state.activeTriple;
        if (state.activeTriple.rings_lon_lat.some(ring => pointInPolygon(location,ring))) return state.activeTriple;
      }
    }
    // The audited marker shares a crowded polar cluster with many catalogue
    // candidates. Give its visible green target a usable hit area.
    if (!state.activeTriple) {
      if (rejectedPair) {
        const marker=project(...rejectedPair.center_lon_lat);
        if(marker.depth>0 && Math.hypot(x-marker.x,y-marker.y)<24) return rejectedPair;
      }
      if (auditedCluster) {
        const marker=project(...auditedCluster.center_lon_lat);
        if (marker.depth>0 && Math.hypot(x-marker.x,y-marker.y)<20)
          return {...auditedCluster,kind:"CATALOGUE_TRIPLE_GLOBAL",globalMask:!auditedCluster.rings_lon_lat?.length};
      }
    }
    for (const cluster of clusters) {
      const marker=project(...cluster.center_lon_lat);
      if (marker.depth>0 && Math.hypot(x-marker.x,y-marker.y)<11)
        return {...cluster, kind:"CATALOGUE_TRIPLE_GLOBAL", globalMask:!cluster.rings_lon_lat?.length};
    }
    const regions=state.activeTriple && !state.activeTriple.globalMask ? [state.activeTriple] : tripleRegions;
    const location=geographicPoint(x,y);
    if (location) {
      for (const region of regions) {
        if (project(...region.center_lon_lat).depth<=0) continue;
        if (region.rings_lon_lat.some(ring => pointInPolygon(location,ring))) return region;
      }
    }
    let nearest=null,distance=14;
    for (const region of regions) {
      const marker=project(...region.center_lon_lat);
      if (marker.depth<=0) continue;
      const candidate=Math.hypot(x-marker.x,y-marker.y);
      if (candidate<distance) {nearest=region;distance=candidate;}
    }
    return nearest || globalTripleAt(location);
  }
  function frame() {
    const delta=((state.targetLongitude-state.longitude+540)%360)-180;
    state.longitude+=delta*.11;
    state.latitude+=(state.targetLatitude-state.latitude)*.11;
    if (state.pendingZoom && Math.abs(delta)<2 && Math.abs(state.targetLatitude-state.latitude)<2) {
      state.targetRadius=state.pendingZoom;
      state.pendingZoom=0;
    }
    const radialDelta = state.targetRadius-state.radius;
    const zoomingIn = radialDelta>0 && Boolean(state.selected || state.activeTriple);
    state.radius += zoomingIn ? Math.min(radialDelta*.09, state.radius*.08) : radialDelta*.11;
    if (state.spinning && !state.drag) {
      const effectiveRadius=Math.max(state.radius,state.targetRadius,state.pendingZoom || 0,1);
      const zoomAdjustedSpin=clamp(baseRadius()/effectiveRadius,.0025,1);
      state.targetLongitude+=.025*zoomAdjustedSpin;
    }
    renderer.draw(moon.width,moon.height,state.longitude,state.latitude,state.radius*state.pixelRatio,state.tripleMode && !state.activeTriple,state.tripleMode && state.activeTriple);
    context.clearRect(0,0,state.width,state.height);
    drawFootprints();
    drawTripleRegions();
    const auditedTarget=$("auditedTarget");
    const auditedMarker=auditedCluster ? project(...auditedCluster.center_lon_lat) : null;
    auditedTarget.hidden=!(state.tripleMode&&!state.activeTriple&&auditedMarker?.depth>0);
    if (!auditedTarget.hidden) {
      auditedTarget.style.left=`${auditedMarker.x}px`;
      auditedTarget.style.top=`${auditedMarker.y}px`;
    }
    const rejectedTarget=$("rejectedTarget");
    const rejectedMarker=rejectedPair ? project(...rejectedPair.center_lon_lat) : null;
    rejectedTarget.hidden=!(state.tripleMode&&!state.activeTriple&&rejectedMarker?.depth>0);
    if(!rejectedTarget.hidden){
      rejectedTarget.style.left=`${rejectedMarker.x}px`;
      rejectedTarget.style.top=`${rejectedMarker.y}px`;
    }
    $("coordinates").textContent=`${((state.longitude%360)+360)%360|0}° E · ${Math.abs(state.latitude).toFixed(1)}° ${state.latitude<0?"S":"N"}`;
    requestAnimationFrame(frame);
  }
  frame();

  $("sensorButtons").onclick=event => {
    const button=event.target.closest("button[data-sensor]");
    if (!button) return;
    const sensor=button.dataset.sensor;
    if (state.tripleMode) setTripleMode(false);
    if (state.visible.has(sensor)) state.visible.delete(sensor);
    else state.visible.add(sensor);
    if (state.selected) {
      state.selected=null;state.pendingZoom=0;state.targetRadius=baseRadius();clearDetails();
    }
    updateButtons();
  };
  $("tripleToggle").onclick=() => setTripleMode(!state.tripleMode);
  $("reset").onclick=() => {
    if (state.tripleMode) setTripleMode(false);
    state.longitude=state.targetLongitude=10;
    state.latitude=state.targetLatitude=-25;
    state.radius=state.targetRadius=baseRadius();
    state.pendingZoom=0;
    state.selected=null;
    state.activeTriple=null;
    state.tripleReturn=null;
    state.overlapReturn=null;
    $("productSearch").value="";
    clearDetails();
  };
  $("zoomOut").onclick=zoomOut;
  $("spin").onclick=() => {
    state.spinning=!state.spinning;
    $("spin").textContent=state.spinning?"Ⅱ   Pause rotation":"▶   Auto rotate";
  };
  let scienceProof=null,negativeControls=null,rejectedProof=null,evidenceCase=null,evidenceCloseTimer=null;
  function syncVerifyButton(){
    $("verifyOverlap").hidden=!state.activeTriple;
    $("verifyOverlap").innerHTML="◈ &nbsp; Scientific verification";
  }
  function closeEvidence(){
    $("workspace").classList.remove("has-evidence");
    $("evidencePanel").setAttribute("aria-hidden","true");
    $("evidencePanel").inert=true;
    clearTimeout(evidenceCloseTimer);
    evidenceCloseTimer=setTimeout(()=>{if(!$("workspace").classList.contains("has-evidence"))$("evidencePanel").hidden=true},900);
    evidenceCase=null;
    if (state.evidenceZoomFactor) {
      state.targetRadius=baseRadius()*state.evidenceZoomFactor;
      state.pendingZoom=0;
      state.evidenceZoomFactor=0;
    }
  }
  function openEvidence(){
    clearTimeout(evidenceCloseTimer);
    const globePanel=$("globeWrap").parentElement;
    const before=$("globeWrap").getBoundingClientRect();
    $("evidencePanel").hidden=false;
    $("evidencePanel").inert=false;
    $("evidencePanel").setAttribute("aria-hidden","false");
    // Commit the off-screen, transparent state before revealing the panel.
    $("evidencePanel").getBoundingClientRect();
    $("workspace").classList.add("has-evidence");
    // FLIP the live globe: render once at its final size, then animate its
    // position and apparent scale from the previous view. Repeated WebGL
    // canvas reallocations during a grid-width animation caused visible jumps.
    if (matchMedia("(min-width: 681px)").matches) {
      const after=$("globeWrap").getBoundingClientRect();
      const beforeBase=Math.min(before.width,before.height);
      const afterBase=Math.min(after.width,after.height);
      const scale=beforeBase/Math.max(afterBase,1);
      const dx=before.left+before.width/2-after.left-after.width/2;
      const dy=before.top+before.height/2-after.top-after.height/2;
      globePanel.style.transition="none";
      globePanel.style.transform=`translate(${dx}px,${dy}px) scale(${scale})`;
      globePanel.getBoundingClientRect();
      globePanel.style.transition="";
      requestAnimationFrame(()=>{globePanel.style.transform=""});
    }
  }
  function evidenceLinks(){
    return `<div class="ev-source"><a class="ev-report-pdf" href="/static/assets/reports/LunaCorr_REALPAIR005_Registered_Local_Scientific_Report.pdf" download>Download report · PDF ↓</a><a href="/science-evidence/ALIGNED_MIDDLE_SCIENTIFIC_VERIFICATION.md" target="_blank" rel="noopener">Full audit text ↗</a><a href="/science-evidence/aligned_middle_decision.json" target="_blank" rel="noopener">Frozen decision ↗</a><a href="/science-evidence/aligned_middle_sha256_v2.txt" target="_blank" rel="noopener">Checksums ↗</a></div>`;
  }
  function reportDocument(kind){
    const registered=kind==="registered";
    const label=registered ? "REALPAIR005 · REGISTERED LOCAL ROI" : "REALPAIR001 · REJECTED CONSISTENCY";
    const pdf=registered ? "LunaCorr_REALPAIR005_Registered_Local_Scientific_Report.pdf" : "LunaCorr_REALPAIR001_Rejected_Consistency_Scientific_Report.pdf";
    const prefix=registered ? "registered" : "rejected";
    return `<section class="ev-report-document ${registered?"":"rejected"}" aria-label="${label} audit report"><div class="ev-report-document-head"><div><strong>▤ &nbsp; AUDIT REPORT</strong><small>${label} · 2 pages</small></div><a href="/static/assets/reports/${pdf}" download>Download PDF ↓</a></div><div class="ev-report-pages" tabindex="0" aria-label="Scroll through both report pages">${[1,2].map(page=>`<figure><a href="/static/assets/reports/${prefix}-page-${page}.png" target="_blank" rel="noopener" aria-label="Open ${label} report page ${page} at full size"><img src="/static/assets/reports/${prefix}-page-${page}.png" alt="${label} audit report page ${page} of 2" loading="${page===1?"eager":"lazy"}"></a><figcaption>PAGE ${page} / 2 · CLICK TO ENLARGE</figcaption></figure>`).join("")}</div></section>`;
  }
  function setEvidenceTab(name){
    document.querySelectorAll(".evidence-tabs button").forEach(button=>button.setAttribute("aria-selected",String(button.dataset.stage===name)));
    document.querySelectorAll(".evidence-stage").forEach(section=>section.hidden=section.dataset.stage!==name);
  }
  function evidenceCircuit(mode){
    const gates={
      registered:[["PDS4 overlap","PASS"],["Camera + DTM","PASS"],["SIFT","PASS"],["AKAZE","PASS"],["Cycle + spread","PASS"]],
      rejected:[["PDS4 overlap","PASS"],["Terrain check","FAIL"],["SIFT","FAIL"],["AKAZE","LIMITED"],["Spatial spread","FAIL"]],
      pending:[["Catalogue polygon","PASS"],["Camera + DTM","UNTESTED"],["SIFT","UNTESTED"],["AKAZE","UNTESTED"],["Cycle + spread","UNTESTED"]],
    }[mode];
    return `<div class="ev-circuit"><div class="ev-circuit-head"><strong>THE EVIDENCE CIRCUIT</strong><small>Every gate must hold for its claimed scope</small></div><div class="ev-circuit-track">${gates.map(([label,status],index)=>`<div class="ev-circuit-gate ${status.toLowerCase()}"><small>0${index+1} · ${label}</small><b>${status==="PASS"?"✓":status==="FAIL"?"×":status==="LIMITED"?"!":"?"}</b><span>${status}</span></div>`).join("")}</div></div>`;
  }
  function matcherDetail(name,metrics){
    const ratio=(metrics.heldout_inlier_ratio*100).toFixed(1);
    const hull=(metrics.hull_fraction*100).toFixed(1);
    return `<div class="ev-matcher-hero"><div><small>FROZEN HELD-OUT TEST</small><strong>${metrics.heldout_inliers} / ${metrics.heldout_candidates}</strong><span>${ratio}% accepted after geometric verification</span></div><div class="ev-matcher-bar"><i style="width:${Math.min(100,Number(ratio))}%"></i><mark>40% gate</mark></div></div>
      <img class="ev-figure ev-matcher-image" src="/science-evidence/science_roi_aligned_middle_test/${name}/inliers_preview.png" alt="Saved ${name} science-pixel inlier preview on the TMC-2 ortho">
      <div class="ev-image-caption"><span>GREEN · VERIFIED INLIERS</span><span>AMBER · REJECTED MATCHES</span></div>
      <div class="ev-metric-grid"><div><small>ALL INLIERS</small><b>${metrics.all_inliers}</b><em>not unique GCPs</em></div><div><small>RMSE · TMC 5 M GRID</small><b>${Number(metrics.rmse_tmc_5m_px).toFixed(2)} px</b><em>local relative fit</em></div><div><small>SPATIAL COVERAGE</small><b>${metrics.occupied_cells_3x6}/18</b><em>${hull}% hull</em></div></div>
      <p class="ev-note">${name} passes the frozen held-out, coverage and reverse-closure gates for this local ROI. Median reverse closure: ${Number(metrics.heldout_cycle_median_5m_px).toFixed(2)} TMC 5 m pixels. These figures do not certify the full strip or absolute ground accuracy.</p><div class="ev-source"><a href="/science-evidence/science_roi_aligned_middle_test/${name}/metrics.json" target="_blank" rel="noopener">${name} frozen metrics ↗</a><a href="/science-evidence/science_roi_aligned_middle_test/${name}/inliers.csv" target="_blank" rel="noopener">Inlier table ↗</a></div>`;
  }
  function renderRejectedEvidence(){
    $("evidencePanel").querySelector(".evidence-head small").textContent="REAL DATA · FROZEN AUDIT";
    const ids=`<div class="evidence-ids"><div><b>OHRC</b><span>${rejectedOhrc}</span></div><div><b>TMC-2</b><span>${auditedTmc}</span></div></div>`;
    if (!rejectedProof) {
      $("evidenceContent").innerHTML=`<div class="evidence-kicker">REALPAIR001 · EARLIER CANDIDATE</div>${ids}<p class="evidence-intro">Loading the frozen rejection audit…</p>`;
      fetch("/rejected-evidence/audit_summary.json")
        .then(response=>{if(!response.ok)throw Error(`Audit unavailable (${response.status})`);return response.json()})
        .then(proof=>{rejectedProof=proof;if(evidenceCase==="rejected")renderRejectedEvidence()})
        .catch(error=>{$("evidenceContent").innerHTML=`${ids}<div class="ev-muted">Rejected-pair audit unavailable: ${escapeHtml(error.message)}</div>`});
      return;
    }
    const proof=rejectedProof;
    $("evidenceContent").innerHTML=`
      <div class="evidence-kicker">${escapeHtml(proof.audit_id)} · REAL SCIENCE DATA</div>
      <h3 class="evidence-title">The earlier pair fails the consistency check.</h3>
      <p class="evidence-intro">This OHRC image and the TMC-2 ortho have a real footprint overlap, but the independent terrain geometry does not support the image-derived correspondence. Illumination and shadows complicate matching; they were not established as the sole failure cause.</p>
      ${ids}
      <div class="ev-verdict rejected"><div><strong>REJECTED · CONSISTENCY</strong><small>Accepted science control points: ${proof.accepted_science_control_points}</small></div><span class="ev-ring">×</span></div>
      ${reportDocument("rejected")}
      ${evidenceCircuit("rejected")}
      <img class="ev-compare" src="/rejected-preview/science_comparison.png" alt="Real OHRC and TMC-2 science images at corresponding map coordinates from the earlier camera audit">
      <div class="ev-image-caption"><span>OHRC · CAMERA/DTM PROJECTION</span><span>TMC-2 ORTHO · SAME MAP COORDINATES</span></div>
      <p class="ev-note">Saved visual from the earlier camera audit; the final v5 rejection metrics below use the adjusted camera. This comparison alone does not validate pixel correspondence.</p>
      <div class="ev-match-lab"><div class="ev-match-lab-head"><strong>PUT THE MATCHERS ON TRIAL</strong><small>Tap each method to see the gate that breaks</small></div><div class="ev-matcher-switch" role="group" aria-label="Inspect rejected-pair matcher"><button type="button" data-rejected-matcher="SIFT" aria-pressed="true">SIFT</button><button type="button" data-rejected-matcher="AKAZE" aria-pressed="false">AKAZE</button></div><div id="rejectedMatcherDetail"></div></div>
      <div class="ev-metric-grid"><div><small>IMAGE-DERIVED SHIFT</small><b>${(proof.descriptor_displacement.akaze_median_m/1000).toFixed(2)} km</b><em>not a camera correction</em></div><div><small>INDEPENDENT ASP ALIGNMENT</small><b>${(proof.pc_align.translation_magnitude_m/1000).toFixed(2)} km</b><em>terrain estimate</em></div><div><small>ACCEPTED CONTROL POINTS</small><b>0</b><em>geometry/image disagree</em></div></div>
      <p class="ev-note">Both matchers can favor repeated crater patterns. SIFT fails frozen held-out support; AKAZE passes point-count support but fails spatial coverage. The ~6.97 km image hypothesis also conflicts with the ~0.65 km independent terrain estimate.</p>
      <div class="ev-source"><a href="/rejected-evidence/SCIENTIFIC_REPORT.md" target="_blank" rel="noopener">Full scientific report ↗</a><a href="/rejected-evidence/audit_summary.json" target="_blank" rel="noopener">Frozen findings ↗</a><a href="/rejected-evidence/checksums.sha256" target="_blank" rel="noopener">Artifact checksums ↗</a></div>
      <p class="ev-note">The rejected result is the proof that LunaCorr can refuse a visually tempting match.</p>`;
    const details={
      SIFT:`<div class="ev-rejected-result"><b class="ev-fail">0 / 6 held-out inliers</b><span>0.0% versus the frozen ≥40% gate</span><p>Training: ${escapeHtml(proof.sift.training)}. Only ${escapeHtml(proof.sift.coverage_cells)} spatial cells. SIFT does not qualify a control network here.</p></div>`,
      AKAZE:`<div class="ev-rejected-result"><b>25 / 50 held-out inliers</b><span>50.0% point support passes</span><p>But the match hull covers only ${(proof.akaze.hull_fraction*100).toFixed(1)}% of the ROI, below the frozen 15% coverage gate. Independent terrain alignment also disagrees with the descriptor shift.</p></div>`,
    };
    const showRejectedMatcher=name=>{
      $("evidenceContent").querySelectorAll("[data-rejected-matcher]").forEach(button=>button.setAttribute("aria-pressed",String(button.dataset.rejectedMatcher===name)));
      $("rejectedMatcherDetail").innerHTML=details[name];
    };
    $("evidenceContent").querySelectorAll("[data-rejected-matcher]").forEach(button=>button.onclick=()=>showRejectedMatcher(button.dataset.rejectedMatcher));
    showRejectedMatcher("SIFT");
  }
  function renderEvidence(){
    if (evidenceCase==="rejected" || state.activeTriple?.kind==="AUDITED_PAIR_REJECTED") {renderRejectedEvidence();return;}
    const region=state.activeTriple;
    if (!region) return;
    const ids=region.product_ids.map(id=>byId.get(id)).filter(Boolean);
    const identity=`<div class="evidence-ids">${ids.map(product=>`<div><b>${escapeHtml(product.sensor)}</b><span>${escapeHtml(product.product_id)}</span></div>`).join("")}</div>`;
    const audited=region.product_ids.includes(auditedOhrc)&&region.product_ids.includes(auditedTmc);
    if (!audited) {
      $("evidencePanel").querySelector(".evidence-head small").textContent="CATALOGUE · NO PIXEL AUDIT";
      $("evidenceContent").innerHTML=`<div class="evidence-kicker">CATALOGUE INTERSECTION · IMAGE TEST PENDING</div><h3 class="evidence-title">The Moon has a suspect, not a match.</h3><p class="evidence-intro">These three saved catalogue footprints intersect. No checksum-verified SIFT or AKAZE science-pixel experiment exists for this exact selection, so the image-evidence gates remain dark.</p>${identity}<div class="ev-verdict pending"><div><strong>ABSTAIN</strong><small>Footprints alone cannot certify corresponding pixels.</small></div><span class="ev-ring">!</span></div>${evidenceCircuit("pending")}<div class="ev-challenge"><strong>THE CLAIM STOPS HERE</strong><p>A bright intersection on the globe is only a search target. LunaCorr will not light the SIFT, AKAZE, or consistency gates without a frozen run on the actual science pixels.</p></div>`;
      return;
    }
    $("evidencePanel").querySelector(".evidence-head small").textContent="REAL DATA · FROZEN AUDIT";
    if (!scienceProof || !negativeControls) {
      $("evidenceContent").innerHTML=`${identity}<p class="evidence-intro">Checking frozen science artifacts and checksums…</p>`;
      Promise.all([fetch("/api/science-proof.json").then(response=>{if(!response.ok)throw Error(`Science proof integrity check failed (${response.status})`);return response.json()}),fetch("/science-evidence/negative_controls_aligned_middle/metrics.json").then(response=>{if(!response.ok)throw Error("Negative controls unavailable");return response.json()})])
        .then(([proof,controls])=>{scienceProof=proof;negativeControls=controls;if(state.activeTriple===region&&!$("evidencePanel").hidden)renderEvidence()})
        .catch(error=>{$("evidenceContent").innerHTML=`${identity}<div class="ev-muted">Evidence unavailable: ${escapeHtml(error.message)}. No registration claim can be shown.</div>`});
      return;
    }
    const {decision,sift,akaze,geometry}=scienceProof;
    const number=(value,digits=1)=>Number(value).toFixed(digits);
    const controls=negativeControls.runs.filter(run=>run.algorithm==="SIFT");
    $("evidenceContent").innerHTML=`
      <div class="evidence-kicker">${escapeHtml(decision.audit_id)} · CHECKSUM VERIFIED</div>
      <h3 class="evidence-title">The overlap survives the challenge.</h3>
      <p class="evidence-intro">OHRC and TMC-2 show the same local terrain after camera/DTM projection. This decision applies only to the audited middle ROI; the IIRS footprint here remains a catalogue intersection.</p>
      ${identity}
      <div class="ev-verdict"><div><strong>REGISTERED · LOCAL OHRC ↔ TMC-2</strong><small>Full strip and absolute ground accuracy: ABSTAIN</small></div><span class="ev-ring">✓</span></div>
      ${reportDocument("registered")}
      ${evidenceCircuit("registered")}
      <div class="evidence-tabs" role="tablist"><button type="button" data-stage="matches" aria-selected="true">SIFT / AKAZE</button><button type="button" data-stage="terrain" aria-selected="false">Terrain swipe</button><button type="button" data-stage="controls" aria-selected="false">Wrong regions</button><button type="button" data-stage="limits" aria-selected="false">Audit limits</button></div>
      <section class="evidence-stage" data-stage="terrain" hidden><div class="evidence-visual"><img src="/science-evidence/science_roi_aligned_middle/tmc_ortho_5m.png" alt="TMC-2 real ortho ROI"><img class="ev-overlay-image" src="/science-evidence/science_roi_aligned_middle/ohrc_projected_5m.png" alt="OHRC projected science ROI"><div class="ev-divider"></div><input type="range" id="evidenceSwipe" min="0" max="100" value="50" aria-label="Swipe OHRC against TMC-2"></div><div class="ev-image-caption"><span>OHRC PROJECTED</span><span>TMC-2 ORTHO · 5 M WORKING GRID</span></div><div class="ev-metric-grid"><div><small>TRUE POLYGON OVERLAP</small><b>${number(geometry.xml_vs_xml_intersection_m2/1e6,2)} km²</b><em>PDS4 XML</em></div><div><small>SIFT INLIERS</small><b>${sift.all_inliers}</b><em>${sift.occupied_cells_3x6}/18 cells</em></div><div><small>AKAZE INLIERS</small><b>${akaze.all_inliers}</b><em>${akaze.occupied_cells_3x6}/18 cells</em></div></div><p class="ev-note">The swipe compares saved real science rasters on a common 5 m TMC grid. It is a visual inspection, not an independent accuracy measurement.</p></section>
      <section class="evidence-stage" data-stage="matches"><div class="ev-match-lab"><div class="ev-match-lab-head"><strong>PUT THE MATCHERS ON TRIAL</strong><small>Switch methods; the frozen science-pixel evidence changes with them</small></div><div class="ev-matcher-switch" role="group" aria-label="Inspect registered-pair matcher"><button type="button" data-matcher="SIFT" aria-pressed="true">SIFT <small>${sift.heldout_inliers}/${sift.heldout_candidates} held out</small></button><button type="button" data-matcher="AKAZE" aria-pressed="false">AKAZE <small>${akaze.heldout_inliers}/${akaze.heldout_candidates} held out</small></button></div><div id="matcherDetail"></div></div><ul class="ev-proof-list"><li><span>Frozen support gate</span><b>≥6 train · ≥40% · ≥3 held-out · ≥40%</b></li><li><span>Spatial gate</span><b>≥6/18 cells · ≥15% hull</b></li><li><span>Reverse closure gate</span><b>≤3 px · TMC 5 m grid</b></li></ul></section>
      <section class="evidence-stage" data-stage="controls" hidden><p class="evidence-intro">The same frozen matcher and thresholds were applied to nearby, plausible-looking but incorrect TMC-2 regions. Both fail.</p><div class="ev-controls">${controls.map(control=>`<article><img src="/science-evidence/negative_controls_aligned_middle/${escapeHtml(control.control)}.png" alt="${escapeHtml(control.control)} negative control"><div><b>${escapeHtml(control.control.replaceAll("_"," "))}</b><span>REJECTED</span><small>${control.candidate_count} candidates · ${control.heldout_inliers}/${control.heldout_candidates} held-out · ${control.occupied_cells_3x6}/18 cells</small></div></article>`).join("")}</div><p class="ev-note">Controls test whether repeated crater texture could create a false positive. Their rejection supports this local pair; it does not prove every catalogue overlap.</p></section>
      <section class="evidence-stage" data-stage="limits" hidden><img class="ev-figure" src="/science-evidence/aligned_middle_evidence/local_affine_overlay.png" alt="Saved local affine alignment"><ul class="ev-proof-list"><li><span>Relative local OHRC ↔ TMC-2</span><b>REGISTERED</b></li><li><span>Whole OHRC strip</span><b class="limited">ABSTAIN</b></li><li><span>Absolute 5 m ground accuracy</span><b class="limited">ABSTAIN</b></li><li><span>IIRS pixel registration</span><b class="limited">NOT TESTED HERE</b></li></ul><p class="ev-note">${escapeHtml(decision.reasons_for_limited_scope.join(" "))}</p>${evidenceLinks()}</section>`;
    $("evidenceContent").querySelectorAll(".evidence-tabs button").forEach(button=>button.onclick=()=>setEvidenceTab(button.dataset.stage));
    const showMatcher=name=>{
      $("evidenceContent").querySelectorAll("[data-matcher]").forEach(button=>button.setAttribute("aria-pressed",String(button.dataset.matcher===name)));
      $("matcherDetail").innerHTML=matcherDetail(name,name==="SIFT"?sift:akaze);
    };
    $("evidenceContent").querySelectorAll("[data-matcher]").forEach(button=>button.onclick=()=>showMatcher(button.dataset.matcher));
    showMatcher("SIFT");
    const swipe=$("evidenceSwipe");
    swipe.oninput=()=>{
      const value=Number(swipe.value);
      $("evidenceContent").querySelector(".ev-overlay-image").style.clipPath=`inset(0 ${100-value}% 0 0)`;
      $("evidenceContent").querySelector(".ev-divider").style.left=`${value}%`;
    };
  }
  $("verifyOverlap").onclick=()=>{
    if (!state.activeTriple) return;
    evidenceCase=state.activeTriple.kind==="AUDITED_PAIR_REJECTED" ? "rejected" : null;
    const audited=state.activeTriple.product_ids.includes(auditedOhrc)&&state.activeTriple.product_ids.includes(auditedTmc);
    const rejected=state.activeTriple.kind==="AUDITED_PAIR_REJECTED";
    if (!audited && !rejected && $("evidencePanel").hidden) {
      state.evidenceZoomFactor=state.targetRadius/baseRadius();
      state.pendingZoom=0;
      state.targetRadius=baseRadius()*1.8;
    }
    openEvidence();
    renderEvidence();
  };
  $("closeEvidence").onclick=closeEvidence;
  document.addEventListener("keydown",event=>{if(event.key==="Escape"&&!$("evidencePanel").hidden)closeEvidence()});
  overlay.onpointerdown=event => {
    overlay.setPointerCapture(event.pointerId);
    state.drag={x:event.offsetX,y:event.offsetY,moved:false};
    overlay.classList.add("dragging");
  };
  overlay.onpointermove=event => {
    if (!state.drag) {
      const target=state.tripleMode ? pickTriple(event.offsetX,event.offsetY) : pick(event.offsetX,event.offsetY);
      overlay.style.cursor=target?"pointer":"grab";
      $("hoverTag").hidden=!target || state.tripleMode;
      if (target && !state.tripleMode) {
        $("hoverTag").textContent=target.product_id;
        $("hoverTag").style.left=`${clamp(event.offsetX+14,8,state.width-210)}px`;
        $("hoverTag").style.top=`${clamp(event.offsetY+14,8,state.height-45)}px`;
      }
      return;
    }
    $("hoverTag").hidden=true;
    const dx=event.offsetX-state.drag.x,dy=event.offsetY-state.drag.y;
    if (Math.abs(dx)+Math.abs(dy)>2) state.drag.moved=true;
    if (state.drag.moved) {
      state.targetLongitude-=dx/Math.max(180,state.radius)*degrees*.85;
      state.targetLatitude=clamp(state.targetLatitude+dy/Math.max(180,state.radius)*degrees*.85,-89,89);
      state.longitude=state.targetLongitude;state.latitude=state.targetLatitude;
    }
    state.drag.x=event.offsetX;state.drag.y=event.offsetY;
  };
  function selectTripleRegion(region) {
    if (!region) return;
    if (state.activeTriple?.id===region.id) {zoomOut();return;}
    closeEvidence();
    if (!state.activeTriple) state.tripleReturn={longitude:state.longitude,latitude:state.latitude,radius:baseRadius()};
    const detailedRegion=resolveTripleGeometry(region);
    state.activeTriple=detailedRegion;
    syncVerifyButton();
    if (!$("evidencePanel").hidden) renderEvidence();
    state.targetLongitude=detailedRegion.center_lon_lat[0];
    state.targetLatitude=detailedRegion.center_lon_lat[1];
    const rejected=detailedRegion.kind==="AUDITED_PAIR_REJECTED";
    const audited=detailedRegion.product_ids.includes(auditedOhrc)&&detailedRegion.product_ids.includes(auditedTmc);
    state.pendingZoom=audited ? baseRadius()*180 : rejected ? tripleZoomRadius(detailedRegion) : Math.min(tripleZoomRadius(detailedRegion),baseRadius()*14);
    const ortho=detailedRegion.product_ids.map(id=>byId.get(id)).find(product=>
      product?.sensor==="TMC-2" && product.image_mode==="GEOREFERENCED_ORTHO" && product.image_url);
    const ohrc=audited ? byId.get(auditedOhrc) : rejected ? byId.get(rejectedOhrc) : null;
    drapeChoices=[ohrc,ortho].filter(product=>product?.image_url);
    showGlobeImage(rejected ? (ortho || ohrc) : (ohrc || ortho || null));
    $("selection").hidden=true;
    $("zoomOut").hidden=false;
    $("globeHint").textContent="SCIENTIFIC VERIFICATION FOR THE AUDIT · CLICK OVERLAP AGAIN TO ZOOM OUT";
  }
  $("auditedTarget").onclick=()=>{
    if (auditedCluster && state.tripleMode && !state.activeTriple)
      selectTripleRegion({...auditedCluster,kind:"CATALOGUE_TRIPLE_GLOBAL",globalMask:!auditedCluster.rings_lon_lat?.length});
  };
  $("rejectedTarget").onclick=()=>{
    if(rejectedPair && state.tripleMode && !state.activeTriple)selectTripleRegion(rejectedPair);
  };
  overlay.onpointerup=event => {
    const dragged=state.drag;state.drag=null;overlay.classList.remove("dragging");
    if (dragged&&!dragged.moved) {
      if (state.tripleMode) selectTripleRegion(pickTriple(event.offsetX,event.offsetY));
      else {
        const product=pick(event.offsetX,event.offsetY);
        if(product)focus(product);
      }
    }
  };
  overlay.onpointercancel=() => {state.drag=null;overlay.classList.remove("dragging");};
  overlay.onpointerleave=() => {$("hoverTag").hidden=true;};
  overlay.onwheel=event => {
    event.preventDefault();
    state.targetRadius=clamp(state.targetRadius*Math.exp(-event.deltaY*.0012),120,30000);
  };
}

start().catch(error => showError(error.message));
