// yōgen studio：エピソード一覧と表紙のコラージュエディタ
"use strict";

const $ = (s, el = document) => el.querySelector(s);
const h = (tag, attrs = {}, ...kids) => {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "style" && typeof v === "object") Object.assign(el.style, v);
    else if (k === "html") el.innerHTML = v;
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const c of kids.flat()) if (c != null && c !== false) el.append(c.nodeType ? c : String(c));
  return el;
};
const api = async (url, opt = {}) => {
  const r = await fetch(url, opt);
  const ct = r.headers.get("content-type") || "";
  const body = ct.includes("json") ? await r.json() : await r.blob();
  if (!r.ok) throw Object.assign(new Error(body.error || r.statusText), { body });
  return body;
};

const KIND_NAME = { fill: "色面", artwork: "作品", sticker: "素材", logo: "ロゴ", wordmark: "題字", text: "文字" };
const STATUS_NAME = {
  draft: "企画中", scripted: "台本あり", fact_checked: "事実確認済み", approved: "試写OK",
  scheduled: "予約済み", published: "公開済み",
};
const GRID = 30; // キャンバス座標で30px（1080 = 36マス）

let P = null; // /api/parts
const S = {
  ep: null, cover: { layers: [] }, sel: -1, hist: [], fut: [], dirty: false,
  grid: true, safe: false, mode: "make", tab: "artwork", scale: 0.4,
};
const aspect = {}; // 画像URL → 高さ/幅

// ---------------------------------------------------------------- 共通
function toast(msg, err = false, list = null) {
  const t = $("#toast");
  t.className = "toast" + (err ? " err" : "");
  t.replaceChildren(h("div", {}, msg), list ? h("ul", {}, list.map((x) => h("li", {}, x))) : "");
  t.hidden = false;
  clearTimeout(toast.t);
  toast.t = setTimeout(() => (t.hidden = true), list ? 9000 : 3200);
}
const hex = (k) => P.palette[k].hex;
const fontFamily = (f) => "F_" + f.replace(/\W/g, "_");

function installFonts() {
  const css = P.fonts.map((f) => `@font-face{font-family:${fontFamily(f)};src:url(/fonts/${f});font-display:block}`);
  document.head.append(h("style", {}, css.join("\n")));
}

// ---------------------------------------------------------------- ルーティング
async function route() {
  if (!P) {
    P = await api("/api/parts");
    installFonts();
  }
  const m = location.hash.match(/^#\/cover\/([\w-]+)/);
  if (S.dirty && !(m && S.ep && m[1] === S.ep.id) && !confirm("保存していない変更があります。離れますか？")) {
    history.back();
    return;
  }
  $("#view-list").hidden = !!m;
  $("#view-editor").hidden = !m;
  if (m) await openEditor(m[1]);
  else await showList();
}
window.addEventListener("hashchange", route);
window.addEventListener("beforeunload", (e) => { if (S.dirty) { e.preventDefault(); e.returnValue = ""; } });

// ---------------------------------------------------------------- 一覧
async function showList() {
  S.dirty = false; S.ep = null;
  $("#top-slot").replaceChildren(h("span", { class: "muted" }, "運営管理"));
  const eps = await api("/api/episodes");
  const box = $("#episodes");
  box.replaceChildren(...eps.map(card));
  if (!eps.length) box.append(h("p", { class: "muted" }, "エピソードがありません。`yogen new <id>` で作ってください。"));
}

function card(e) {
  const at = P.pipeline.indexOf(e.status);
  const thumb = e.artworks_ready
    ? h("img", { src: `/api/episodes/${e.id}/cover.jpg?w=360&t=${Date.now()}`, alt: "", loading: "lazy" })
    : h("div", { class: "ph" }, "作品画像が未取得", h("br"), h("code", {}, `yogen fetch ${e.id}`));
  const c = e.claims;
  return h("article", { class: "card" },
    h("a", { class: "thumb", href: `#/cover/${e.id}`, title: "表紙をつくる" }, thumb),
    h("div", { class: "body" },
      h("div", { class: "id" }, e.id),
      h("h2", {}, e.title),
      h("div", { class: "pipe", title: P.pipeline.map((s) => STATUS_NAME[s]).join(" → ") },
        P.pipeline.map((s, i) => h("i", { class: i < at ? "done" : i === at ? "now" : "" }))),
      h("div", { class: "meta" },
        h("span", { class: "chip" }, STATUS_NAME[e.status] || e.status),
        c ? h("span", { class: "chip " + (c.verified === c.total ? "ok" : "warn") }, `事実確認 ${c.verified}/${c.total}`)
          : h("span", { class: "chip" }, "台本なし"),
        h("span", { class: "chip" }, "公開 " + (e.publish_at || "未定")),
        h("span", { class: "chip " + (e.has_cover ? "ok" : "") }, e.has_cover ? "表紙あり" : "表紙なし"),
        h("span", { class: "chip" }, e.colors.map((k) => h("span", { class: "swatch", style: { background: hex(k) }, title: P.palette[k].name })))),
      h("div", { class: "row" }, h("a", { href: `#/cover/${e.id}` }, h("button", { class: "primary" }, "表紙をつくる")))));
}

// ---------------------------------------------------------------- エディタ：開く
async function openEditor(id) {
  if (S.ep && S.ep.id === id) return;
  S.ep = await api(`/api/episodes/${id}`);
  S.cover = S.ep.cover;
  S.sel = -1; S.hist = []; S.fut = []; S.dirty = !S.ep.cover_saved; S.mode = "make";
  S.tab = "artwork";
  // 作品の縦横比は episode.yaml の値から
  for (const a of S.ep.artworks) if (a.width && a.height) aspect[artUrl(a.key)] = a.height / a.width;
  buildTop();
  buildTray();
  fitStage();
  render();
  if (!S.ep.cover_saved) toast("雛形を置きました。動かして「保存」すると cover.yaml になります");
}

function buildTop() {
  const seg = h("div", { class: "seg" },
    h("button", { id: "m-make", onclick: () => setMode("make") }, "つくる"),
    h("button", { id: "m-check", onclick: () => setMode("check") }, "たしかめる"));
  $("#top-slot").replaceChildren(
    h("a", { href: "#/" }, h("button", {}, "← 一覧")),
    h("span", { class: "title" }, S.ep.working_title || S.ep.title),
    h("span", { id: "dirty", class: "dirty-dot", title: "未保存", hidden: true }),
    h("span", { class: "spacer" }),
    seg,
    h("button", { id: "b-undo", onclick: undo, title: "取り消し ⌘Z" }, "↶"),
    h("button", { id: "b-redo", onclick: redo, title: "やり直し ⇧⌘Z" }, "↷"),
    h("button", { id: "b-grid", onclick: () => { S.grid = !S.grid; render(); } }, "マス目"),
    h("button", { id: "b-safe", onclick: () => { S.safe = !S.safe; render(); } }, "隠れる範囲"),
    h("button", { class: "primary", onclick: save }, "保存"),
    h("button", { onclick: exportPng, title: "build/cover.png に書き出す" }, "書き出し"));
}

// ---------------------------------------------------------------- パーツの棚
const TABS = [["artwork", "作品"], ["sticker", "素材"], ["fill", "色面"], ["text", "文字"], ["brand", "ロゴ"]];

function buildTray() {
  $("#tray-tabs").replaceChildren(...TABS.map(([k, name]) =>
    h("button", { class: S.tab === k ? "on" : "", onclick: () => { S.tab = k; buildTray(); } }, name)));
  const tiles = [];
  const W = P.canvas.width;
  if (S.tab === "artwork") {
    for (const a of S.ep.artworks) {
      tiles.push(tile(
        a.ready ? h("img", { src: artUrl(a.key) }) : h("span", { class: "muted" }, "未取得"),
        `${a.key}${a.artist ? " · " + a.artist : ""}`,
        { kind: "artwork", artwork: a.key, w: W * 0.7 }, !a.ready,
        a.ready ? null : `先に yogen fetch ${S.ep.id}`));
    }
  } else if (S.tab === "sticker") {
    for (const s of P.stickers) {
      tiles.push(tile(
        s.thumb ? h("img", { src: s.thumb, class: "mono" }) : h("span", {}, s.key),
        s.note || s.key, { kind: "sticker", sticker: s.key, index: s.index, w: 340 }));
    }
  } else if (S.tab === "fill") {
    for (const k of S.ep.colors) {
      tiles.push(tile(h("div", { class: "blk", style: { background: hex(k) } }),
        P.palette[k].name, { kind: "fill", color: k, w: W * 1.2, h: 420, rot: -6 }));
    }
  } else if (S.tab === "text") {
    tiles.push(tile(h("span", { class: "txt" }, "Aa"), "題（英語）",
      { kind: "text", text: "TITLE", size: 120, color: "gofun", font: "archivo/Archivo-ExpandedBlack.ttf" }));
    tiles.push(tile(h("span", { class: "txt", style: { color: hex(S.ep.colors[0]) } }, "Aa"), "差し色の文字",
      { kind: "text", text: "TITLE", size: 120, color: S.ep.colors[0], font: "contrast/Shrikhand.ttf" }));
  } else if (S.tab === "brand") {
    tiles.push(tile(h("img", { src: "/api/part/wordmark.png" }), "題字 yōgen（藤黄の札）", { kind: "wordmark", w: 420 }));
    tiles.push(tile(h("img", { src: "/api/part/logo/gofun.png" }), "篆書「妖幻」", { kind: "logo", w: 260 }));
  }
  $("#tray-body").replaceChildren(...tiles);
}

function tile(pic, label, proto, disabled = false, why = null) {
  const el = h("div", { class: "tile" + (disabled ? " disabled" : ""), draggable: !disabled, title: why || label },
    h("div", { class: "pic" }, pic), h("div", {}, label));
  if (disabled) return el;
  el.addEventListener("dragstart", (e) => {
    e.dataTransfer.setData("application/x-yogen", JSON.stringify(proto));
    e.dataTransfer.effectAllowed = "copy";
  });
  el.addEventListener("click", () => addLayer(proto, P.canvas.width / 2, P.canvas.height / 2));
  return el;
}

function addLayer(proto, x, y) {
  setMode("make");
  commit(() => {
    const l = { ...proto, x: snap(x), y: snap(y) };
    if (l.kind !== "text" && l.rot == null) l.rot = 0;
    S.cover.layers.push(l);
    S.sel = S.cover.layers.length - 1;
  });
}

// ---------------------------------------------------------------- ステージ
function fitStage() {
  const wrap = $("#stage-wrap");
  const { width: W, height: H } = P.canvas;
  const sc = Math.min((wrap.clientWidth - 60) / W, (wrap.clientHeight - 60) / H);
  S.scale = Math.max(0.15, sc);
  const st = $("#stage");
  st.style.width = W * S.scale + "px";
  st.style.height = H * S.scale + "px";
  const g = GRID * S.scale;
  $("#grid").style.background =
    `linear-gradient(#ffffff14 1px, transparent 1px) 0 0/${g}px ${g}px,` +
    `linear-gradient(90deg, #ffffff14 1px, transparent 1px) 0 0/${g}px ${g}px,` +
    `linear-gradient(90deg, transparent calc(50% - 1px), #e8b32655 calc(50% - 1px), #e8b32655 calc(50% + 1px), transparent calc(50% + 1px))`;
}
window.addEventListener("resize", () => { if (S.ep) { fitStage(); render(); } });

const stage = () => $("#stage");
function toCanvas(e) {
  const r = stage().getBoundingClientRect();
  return { x: (e.clientX - r.left) / S.scale, y: (e.clientY - r.top) / S.scale };
}
const snap = (v) => (S.grid ? Math.round(v / GRID) * GRID : Math.round(v));

// 地の判定（cover.py の ground_under と同じ）
function inside(px, py, f) {
  const a = (-f.rot * Math.PI) / 180;
  const dx = px - f.x, dy = py - f.y;
  const lx = dx * Math.cos(a) - dy * Math.sin(a), ly = dx * Math.sin(a) + dy * Math.cos(a);
  return Math.abs(lx) <= f.w / 2 && Math.abs(ly) <= f.h / 2;
}
function groundUnder(i) {
  const l = S.cover.layers[i];
  for (let j = i - 1; j >= 0; j--) {
    const b = S.cover.layers[j];
    if (b.kind === "fill" && inside(l.x, l.y, b)) return b.color;
  }
  return "sumi";
}
const dotInk = (g) => (g === "sumi" ? "gofun" : "sumi");
const artUrl = (key) => `/api/episodes/${S.ep.id}/artwork/${key}.jpg`;

function partUrl(l, i) {
  if (l.kind === "artwork") return artUrl(l.artwork);
  if (l.kind === "sticker") return `/api/part/sticker/${l.sticker}/${l.index || 0}/${dotInk(groundUnder(i))}.png`;
  if (l.kind === "logo") return `/api/part/logo/${dotInk(groundUnder(i))}.png`;
  if (l.kind === "wordmark") return "/api/part/wordmark.png";
  return null;
}

function layerSize(l, url) {
  if (l.kind === "fill") return [l.w, l.h];
  let r = aspect[url] ?? 1;
  if (l.kind === "artwork" && l.crop) r = (r * (l.crop[3] - l.crop[1])) / (l.crop[2] - l.crop[0]);
  return [l.w, l.w * r];
}

function layerEl(l, i) {
  const sc = S.scale;
  const el = h("div", { class: `layer ${l.kind}` + (i === S.sel ? " sel" : ""), "data-i": i });
  const inner = h("div", { class: "inner" });
  el.append(inner);
  inner.style.transform = l.flip ? "scaleX(-1)" : "";
  if (l.kind === "text") {
    Object.assign(inner.style, {
      fontFamily: fontFamily(l.font || "archivo/Archivo-ExpandedBlack.ttf"),
      fontSize: l.size * sc + "px", lineHeight: l.size * sc + "px", paddingBottom: l.size * 0.3 * sc + "px",
      color: hex(l.color || "gofun"),
    });
    inner.textContent = l.text;
    Object.assign(el.style, { left: l.x * sc + "px", top: l.y * sc + "px" });
  } else {
    const url = partUrl(l, i);
    const [w, hh] = layerSize(l, url);
    Object.assign(el.style, { left: (l.x - w / 2) * sc + "px", top: (l.y - hh / 2) * sc + "px", width: w * sc + "px", height: hh * sc + "px" });
    if (l.kind === "fill") inner.style.background = hex(l.color);
    else {
      const img = h("img", { src: url, alt: "" });
      if (l.kind === "artwork" && l.crop) {
        const [cl, ct, cr, cb] = l.crop;
        const iw = w / (cr - cl);
        Object.assign(img.style, { width: iw * sc + "px", left: -cl * iw * sc + "px", top: -ct * (hh / (cb - ct)) * sc + "px" });
      } else Object.assign(img.style, { width: "100%", height: "100%", left: 0, top: 0 });
      if (aspect[url] == null) {
        el.classList.add("loading");
        img.addEventListener("load", () => { aspect[url] = img.naturalHeight / img.naturalWidth; render(); }, { once: true });
        img.addEventListener("error", () => { el.classList.add("loading"); }, { once: true });
      }
      inner.append(img);
    }
  }
  el.style.transform = (l.kind === "text" ? "translate(-50%, -50%) " : "") + `rotate(${l.rot || 0}deg)`;
  if (i === S.sel) {
    el.append(h("div", { class: "handle size", "data-h": "size" }), h("div", { class: "handle rot", "data-h": "rot" }));
  }
  el.addEventListener("pointerdown", (e) => startDrag(e, i));
  return el;
}

function render() {
  if (!S.ep) return;
  const st = stage();
  st.classList.toggle("checking", S.mode === "check");
  st.classList.toggle("show-safe", S.safe);
  $("#grid").style.display = S.grid ? "" : "none";
  $("#layers").replaceChildren(...S.cover.layers.map(layerEl));
  $("#m-make")?.classList.toggle("on", S.mode === "make");
  $("#m-check")?.classList.toggle("on", S.mode === "check");
  $("#b-grid")?.classList.toggle("primary", S.grid);
  $("#b-safe")?.classList.toggle("primary", S.safe);
  $("#b-undo").disabled = !S.hist.length;
  $("#b-redo").disabled = !S.fut.length;
  $("#dirty").hidden = !S.dirty;
  renderInspector();
  renderLayerList();
}

// ---------------------------------------------------------------- ドラッグ（移動・大きさ・回転）
function startDrag(e, i) {
  if (S.mode !== "make" || e.button !== 0) return;
  e.preventDefault();
  e.stopPropagation();
  const mode = e.target.dataset.h || "move";
  if (S.sel !== i) { S.sel = i; render(); }
  const l = S.cover.layers[i];
  const before = JSON.stringify(S.cover);
  const p0 = toCanvas(e);
  const o = { ...l };
  const d0 = Math.hypot(p0.x - l.x, p0.y - l.y) || 1;

  const move = (ev) => {
    const p = toCanvas(ev);
    if (mode === "move") {
      l.x = snap(o.x + p.x - p0.x);
      l.y = snap(o.y + p.y - p0.y);
    } else if (mode === "rot") {
      let a = (Math.atan2(p.y - l.y, p.x - l.x) * 180) / Math.PI + 90;
      if (ev.shiftKey || S.grid) a = Math.round(a / 15) * 15;
      a = ((a + 540) % 360) - 180;
      l.rot = Math.round(a * 10) / 10;
    } else if (l.kind === "fill") {
      const a = (-(l.rot || 0) * Math.PI) / 180;
      const dx = p.x - l.x, dy = p.y - l.y;
      l.w = Math.max(GRID, snap(2 * Math.abs(dx * Math.cos(a) - dy * Math.sin(a))));
      l.h = Math.max(GRID, snap(2 * Math.abs(dx * Math.sin(a) + dy * Math.cos(a))));
    } else {
      const k = Math.max(0.05, Math.hypot(p.x - l.x, p.y - l.y) / d0);
      if (l.kind === "text") l.size = Math.max(12, Math.round(o.size * k));
      else l.w = Math.max(20, Math.round(o.w * k));
    }
    render();
  };
  const up = () => {
    window.removeEventListener("pointermove", move);
    window.removeEventListener("pointerup", up);
    if (JSON.stringify(S.cover) !== before) {
      S.hist.push(before); S.fut = []; S.dirty = true;
    }
    render();
  };
  window.addEventListener("pointermove", move);
  window.addEventListener("pointerup", up);
}

function initStage() {
  const st = stage();
  st.addEventListener("pointerdown", (e) => {
    if (e.target === st || e.target.id === "layers") { S.sel = -1; render(); }
  });
  st.addEventListener("dragover", (e) => { e.preventDefault(); st.classList.add("drop"); });
  st.addEventListener("dragleave", () => st.classList.remove("drop"));
  st.addEventListener("drop", (e) => {
    e.preventDefault();
    st.classList.remove("drop");
    const raw = e.dataTransfer.getData("application/x-yogen");
    if (!raw) return;
    const p = toCanvas(e);
    addLayer(JSON.parse(raw), p.x, p.y);
  });
}

// ---------------------------------------------------------------- 履歴
function commit(fn) {
  S.hist.push(JSON.stringify(S.cover));
  if (S.hist.length > 200) S.hist.shift();
  S.fut = [];
  fn();
  S.dirty = true;
  render();
}
function undo() {
  if (!S.hist.length) return;
  S.fut.push(JSON.stringify(S.cover));
  S.cover = JSON.parse(S.hist.pop());
  S.sel = Math.min(S.sel, S.cover.layers.length - 1);
  S.dirty = true;
  render();
}
function redo() {
  if (!S.fut.length) return;
  S.hist.push(JSON.stringify(S.cover));
  S.cover = JSON.parse(S.fut.pop());
  S.dirty = true;
  render();
}
const cur = () => S.cover.layers[S.sel];
function edit(fn) { if (cur()) commit(() => fn(cur())); }
function moveZ(i, d) {
  const j = i + d, L = S.cover.layers;
  if (j < 0 || j >= L.length) return;
  commit(() => { [L[i], L[j]] = [L[j], L[i]]; if (S.sel === i) S.sel = j; else if (S.sel === j) S.sel = i; });
}
function remove(i) { commit(() => { S.cover.layers.splice(i, 1); S.sel = -1; }); }
function duplicate(i) {
  commit(() => {
    const c = JSON.parse(JSON.stringify(S.cover.layers[i]));
    c.x += GRID * 2; c.y += GRID * 2;
    S.cover.layers.splice(i + 1, 0, c);
    S.sel = i + 1;
  });
}

// ---------------------------------------------------------------- インスペクタ
function num(label, key, step = 1, wide = false) {
  const l = cur();
  return h("label", { class: wide ? "wide" : "" }, label,
    h("input", { type: "number", step, value: Math.round((l[key] ?? 0) * 10) / 10,
      onchange: (e) => edit((x) => { x[key] = parseFloat(e.target.value) || 0; }) }));
}

function swatches(keys, key) {
  const l = cur();
  return h("div", { class: "swatches" }, keys.map((k) =>
    h("button", { class: l[key] === k ? "on" : "", title: P.palette[k].name, style: { background: hex(k) },
      onclick: () => edit((x) => { x[key] = k; }) })));
}

function renderInspector() {
  const box = $("#inspector");
  const l = cur();
  if (!l) {
    box.replaceChildren(h("h3", {}, "選んでいる層"), h("p", { class: "muted small" },
      "ステージの層をクリックすると、ここで数値や色を変えられます。左の棚からドラッグで新しく置けます。"),
      h("div", { class: "note" }, "地は墨で固定。色面はこの回の差し色だけ。素材は色を付けず網点になり、点の色は下の地で自動で決まります。"));
    return;
  }
  const kids = [h("h3", {}, `${KIND_NAME[l.kind]}${l.kind === "sticker" ? `：${l.sticker} #${l.index || 0}` : ""}`)];
  const f = [num("X（中心）", "x"), num("Y（中心）", "y")];
  if (l.kind === "text") f.push(num("文字の大きさ", "size"));
  else f.push(num("幅", "w"));
  if (l.kind === "fill") f.push(num("高さ", "h"));
  f.push(num("回転（度）", "rot", 1));
  kids.push(h("div", { class: "fields" }, f));
  kids.push(h("div", { class: "row", style: { marginTop: "8px" } },
    h("label", { class: "row small" }, h("input", { type: "checkbox", style: { width: "auto" }, checked: !!l.flip,
      onchange: (e) => edit((x) => { x.flip = e.target.checked; }) }), "左右反転"),
    h("span", { style: { flex: 1 } }),
    h("button", { onclick: () => duplicate(S.sel) }, "複製"),
    h("button", { onclick: () => remove(S.sel) }, "削除")));

  if (l.kind === "fill") kids.push(h("h3", { style: { marginTop: "14px" } }, "色"), swatches(S.ep.colors, "color"));
  if (l.kind === "text") {
    kids.push(
      h("h3", { style: { marginTop: "14px" } }, "文"),
      h("textarea", { onchange: (e) => edit((x) => { x.text = e.target.value; }) }, l.text),
      h("h3", { style: { marginTop: "14px" } }, "色"), swatches(["gofun", "sumi", ...S.ep.colors], "color"),
      h("h3", { style: { marginTop: "14px" } }, "書体"),
      h("select", { onchange: (e) => edit((x) => { x.font = e.target.value; }) },
        P.fonts.map((fn) => h("option", { value: fn, selected: fn === l.font }, fn.split("/")[1].replace(".ttf", "")))));
  }
  if (l.kind === "sticker" || l.kind === "logo") {
    const g = groundUnder(S.sel);
    kids.push(h("div", { class: "note" },
      `点の色：${P.palette[dotInk(g)].name}（下の地が${P.palette[g].name}なので）。色面の上に動かすと墨の点に変わります。`));
  }
  if (l.kind === "sticker") {
    const variants = P.stickers.filter((s) => s.key === l.sticker);
    if (variants.length > 1) kids.push(h("div", { class: "row", style: { marginTop: "8px" } }, "版：",
      variants.map((v) => h("button", { class: v.index === (l.index || 0) ? "primary" : "", title: v.note,
        onclick: () => edit((x) => { x.index = v.index; }) }, `#${v.index}`))));
  }
  if (l.kind === "artwork") {
    const a = S.ep.artworks.find((x) => x.key === l.artwork) || {};
    kids.push(h("div", { class: "note" }, `${a.title || l.artwork}${a.artist ? " / " + a.artist : ""}${a.date ? "（" + a.date + "）" : ""}`, h("br"), a.license || ""));
    const crop = l.crop || [0, 0, 1, 1];
    const cropIn = (label, n) => h("label", {}, label, h("input", { type: "number", step: 0.01, min: 0, max: 1, value: crop[n],
      onchange: (e) => edit((x) => {
        const c = [...(x.crop || [0, 0, 1, 1])];
        c[n] = Math.min(1, Math.max(0, parseFloat(e.target.value) || 0));
        x.crop = c[0] === 0 && c[1] === 0 && c[2] === 1 && c[3] === 1 ? undefined : c;
      }) }));
    kids.push(h("h3", { style: { marginTop: "14px" } }, "切り取り（割合）"),
      h("div", { class: "fields" }, cropIn("左", 0), cropIn("上", 1), cropIn("右", 2), cropIn("下", 3)));
  }
  box.replaceChildren(...kids);
}

function layerLabel(l) {
  if (l.kind === "text") return `文字「${l.text.split("\n")[0]}」`;
  if (l.kind === "sticker") return `素材 ${l.sticker} #${l.index || 0}`;
  if (l.kind === "fill") return `色面 ${P.palette[l.color]?.name || l.color}`;
  if (l.kind === "artwork") return `作品 ${l.artwork}`;
  return KIND_NAME[l.kind];
}

function renderLayerList() {
  const L = S.cover.layers;
  const items = L.map((l, i) => h("li", { class: i === S.sel ? "on" : "", onclick: () => { S.sel = i; render(); } },
    l.kind === "fill" ? h("span", { class: "swatch", style: { background: hex(l.color) } }) : null,
    h("span", { class: "nm" }, layerLabel(l)),
    h("button", { title: "手前へ", onclick: (e) => { e.stopPropagation(); moveZ(i, 1); } }, "▲"),
    h("button", { title: "奥へ", onclick: (e) => { e.stopPropagation(); moveZ(i, -1); } }, "▼"))).reverse();
  items.push(h("li", { class: "muted", style: { cursor: "default" } }, h("span", { class: "swatch", style: { background: hex("sumi") } }), "地（墨）"));
  $("#layer-list").replaceChildren(...items);
}

// ---------------------------------------------------------------- たしかめる・保存・書き出し
async function setMode(m) {
  if (S.mode === m) return;
  S.mode = m;
  if (m === "check") {
    S.sel = -1;
    render();
    $("#stage-status").textContent = "書き出しと同じ処理で合成しています…";
    try {
      const blob = await api(`/api/episodes/${S.ep.id}/preview.jpg?w=1080`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(S.cover) });
      if (S.mode !== "check") return;
      const img = $("#preview");
      if (img.src) URL.revokeObjectURL(img.src);
      img.src = URL.createObjectURL(blob);
      $("#stage-status").textContent = "書き出しと同じ見え方です。斜線はショートの画面で隠れやすい範囲（目安）。";
    } catch (e) {
      showError(e);
      S.mode = "make";
      $("#stage-status").textContent = "";
    }
  } else $("#stage-status").textContent = "";
  render();
}

function showError(e) {
  const b = e.body || {};
  toast(e.message, true, b.problems || (b.detail ? [b.detail] : null));
}

async function save() {
  try {
    const r = await api(`/api/episodes/${S.ep.id}/cover`, {
      method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(S.cover) });
    S.dirty = false;
    S.ep.cover_saved = true;
    render();
    toast(`保存しました：${r.saved}`);
    return true;
  } catch (e) { showError(e); return false; }
}

async function exportPng() {
  if (S.dirty && !(await save())) return;
  toast("書き出しています…");
  try {
    const r = await api(`/api/episodes/${S.ep.id}/export`, { method: "POST" });
    toast(`書き出しました：${r.exported}`);
  } catch (e) { showError(e); }
}

// ---------------------------------------------------------------- キー
window.addEventListener("keydown", (e) => {
  if ($("#view-editor").hidden) return;
  if (["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName)) return;
  const mod = e.metaKey || e.ctrlKey;
  if (mod && e.key.toLowerCase() === "z") { e.preventDefault(); e.shiftKey ? redo() : undo(); return; }
  if (mod && e.key.toLowerCase() === "s") { e.preventDefault(); save(); return; }
  if (e.key === " ") { e.preventDefault(); setMode(S.mode === "make" ? "check" : "make"); return; }
  if (S.mode !== "make") return;
  const i = S.sel;
  if (i < 0) return;
  if (mod && e.key.toLowerCase() === "d") { e.preventDefault(); duplicate(i); return; }
  const step = e.shiftKey ? GRID : 1;
  const nudge = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] }[e.key];
  if (nudge) { e.preventDefault(); edit((l) => { l.x += nudge[0]; l.y += nudge[1]; }); return; }
  if (e.key === "Delete" || e.key === "Backspace") { e.preventDefault(); remove(i); return; }
  if (e.key === "[") moveZ(i, -1);
  if (e.key === "]") moveZ(i, 1);
  if (e.key.toLowerCase() === "f") edit((l) => { l.flip = !l.flip; });
  if (e.key === "Escape") { S.sel = -1; render(); }
});

initStage();
route().catch((e) => toast(e.message, true));
