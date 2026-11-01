(() => {
  "use strict";

  /* ------------------------------------------------------------------ config */
  const API = "/api";
  const ASSET_BASE = "/assets/clothes/";
  // O nome do ficheiro pode ter espaços, 'ç' e '_': codificamos sempre.
  const assetUrl = (file) => (file ? ASSET_BASE + encodeURIComponent(file) : null);

  const $ = (sel, root = document) => root.querySelector(sel);

  const state = {
    items: [],
    styles: [],
    filter: "all",
    hoverId: null,
    activeId: null,
    trackIndex: 0,
    detail: null,
    token: 0, // invalida respostas antigas quando o utilizador troca de peça
  };

  const detailCache = new Map();
  const inflight = new Map();

  const rack = $("#rack");
  const scroller = $("#scroller");
  const track = $("#track");
  const statusEl = $("#status");
  const filtersEl = $("#filters");

  const panelEmpty = $("#panel-empty");
  const panelContent = $("#panel-content");
  const playerEl = $("#player");
  const audio = new Audio();
  audio.preload = "none";

  /* ------------------------------------------------------------------ helpers */
  function el(tag, props = {}, ...children) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(props)) {
      if (value == null || value === false) continue;
      if (key === "class") node.className = value;
      else if (key.startsWith("on") && typeof value === "function") node.addEventListener(key.slice(2), value);
      else node.setAttribute(key, value === true ? "" : value);
    }
    for (const child of children.flat()) if (child != null) node.append(child);
    return node;
  }

  async function fetchJSON(url) {
    const resp = await fetch(url, { headers: { Accept: "application/json" } });
    if (!resp.ok) throw new Error(`HTTP ${resp.status} em ${url}`);
    return resp.json();
  }

  function getDetail(id) {
    if (detailCache.has(id)) return Promise.resolve(detailCache.get(id));
    if (inflight.has(id)) return inflight.get(id);
    const promise = fetchJSON(`${API}/items/${id}`)
      .then((data) => {
        detailCache.set(id, data);
        return data;
      })
      .finally(() => inflight.delete(id));
    inflight.set(id, promise);
    return promise;
  }

  const fmtTime = (s) => {
    if (!Number.isFinite(s)) return "0:00";
    const m = Math.floor(s / 60);
    return `${m}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
  };

  /* ------------------------------------------------------------------ filtros */
  function renderFilters() {
    filtersEl.replaceChildren();
    const make = (value, label) =>
      el("button", {
        class: "chip",
        type: "button",
        "aria-pressed": String(state.filter === value),
        onclick: () => {
          state.filter = value;
          renderFilters();
          renderRack();
        },
      }, label);
    filtersEl.append(make("all", `Todos (${state.items.length})`));
    for (const s of state.styles) filtersEl.append(make(s.style, `${s.style} (${s.count})`));
  }

  /* ------------------------------------------------------------------ arara */
  const HANGER_SVG = `
    <svg class="hanger" viewBox="0 0 74 56" fill="none" aria-hidden="true">
      <path d="M37 4c0-3 6-3 6 2s-6 5-6 10v6" stroke="#8a8a93" stroke-width="2.4" stroke-linecap="round"/>
      <path d="M37 22 6 42c-3 2-1 6 2 6h58c3 0 5-4 2-6L37 22Z" stroke="#8a8a93" stroke-width="2.4" stroke-linejoin="round"/>
    </svg>`;

  function visibleItems() {
    return state.filter === "all" ? state.items : state.items.filter((i) => i.style === state.filter);
  }

  function placeholder(text) {
    return el("div", { class: "garment-missing" }, text);
  }

  function buildGarment(item, index) {
    const body = el("div", { class: "hang" });
    body.insertAdjacentHTML("beforeend", HANGER_SVG);

    const src = assetUrl(item.image_file);
    if (src) {
      const img = el("img", { class: "garment-img", src, alt: item.name, loading: "lazy", draggable: "false" });
      img.addEventListener("error", () => img.replaceWith(placeholder(`Imagem não carregou: ${item.file_stem}`)), { once: true });
      body.append(img);
    } else {
      body.append(placeholder(`Sem ficheiro para “${item.file_stem}”`));
    }
    body.append(el("div", { class: "garment-label" }, item.name));

    const sway = el("div", { class: "sway" }, body);
    const btn = el("button", {
      class: "garment",
      type: "button",
      role: "listitem",
      "data-id": String(item.id),
      "aria-pressed": "false",
      "aria-label": `${item.name}, ${item.brand}, estilo ${item.style}`,
    }, sway);
    btn.style.setProperty("--delay", `${-(index % 7) * 0.7}s`);
    btn.style.setProperty("--dur", `${5 + (index % 4)}s`);

    let prefetchTimer = null;
    btn.addEventListener("pointerenter", (e) => {
      if (e.pointerType !== "mouse") return;
      state.hoverId = item.id;
      updateFocus();
      clearTimeout(prefetchTimer);
      prefetchTimer = setTimeout(() => getDetail(item.id).catch(() => {}), 150);
    });
    btn.addEventListener("pointermove", (e) => {
      if (e.pointerType !== "mouse") return;
      const r = body.getBoundingClientRect();
      const px = (e.clientX - r.left) / r.width - 0.5;
      const py = (e.clientY - r.top) / r.height - 0.5;
      body.style.setProperty("--ry", `${(px * 14).toFixed(2)}deg`);
      body.style.setProperty("--rx", `${(-py * 10).toFixed(2)}deg`);
    });
    btn.addEventListener("pointerleave", () => {
      clearTimeout(prefetchTimer);
      body.style.setProperty("--ry", "0deg");
      body.style.setProperty("--rx", "0deg");
      if (state.hoverId === item.id) state.hoverId = null;
      updateFocus();
    });
    btn.addEventListener("focus", () => {
      state.hoverId = item.id;
      updateFocus();
    });
    btn.addEventListener("blur", () => {
      if (state.hoverId === item.id) state.hoverId = null;
      updateFocus();
    });
    return btn;
  }

  function renderRack() {
    track.replaceChildren(...visibleItems().map(buildGarment));
    statusEl.textContent = visibleItems().length ? "" : "Nenhuma peça neste estilo.";
    updateFocus();
  }

  function updateFocus() {
    const focusId = state.hoverId ?? state.activeId;
    rack.classList.toggle("focusing", focusId != null);
    for (const g of track.querySelectorAll(".garment")) {
      const id = Number(g.dataset.id);
      g.classList.toggle("is-focus", id === focusId);
      g.classList.toggle("is-active", id === state.activeId);
      g.setAttribute("aria-pressed", String(id === state.activeId));
    }
  }

  function centerOn(id) {
    const node = track.querySelector(`.garment[data-id="${id}"]`);
    if (!node) return;
    const left = node.offsetLeft - (scroller.clientWidth - node.offsetWidth) / 2;
    scroller.scrollTo({ left: Math.max(0, left), behavior: "smooth" });
  }

  /* ----- navegação: setas, roda do rato, arrastar, teclado ----- */
  $("#prev").addEventListener("click", () => scroller.scrollBy({ left: -scroller.clientWidth * 0.7, behavior: "smooth" }));
  $("#next").addEventListener("click", () => scroller.scrollBy({ left: scroller.clientWidth * 0.7, behavior: "smooth" }));

  scroller.addEventListener("wheel", (e) => {
    if (Math.abs(e.deltaY) <= Math.abs(e.deltaX)) return;
    const max = scroller.scrollWidth - scroller.clientWidth;
    if ((e.deltaY < 0 && scroller.scrollLeft <= 0) || (e.deltaY > 0 && scroller.scrollLeft >= max - 1)) return;
    e.preventDefault();
    scroller.scrollLeft += e.deltaY;
  }, { passive: false });

  let drag = null;
  let suppressClick = false;
  scroller.addEventListener("pointerdown", (e) => {
    if (e.pointerType !== "mouse" || e.button !== 0) return;
    drag = { x: e.clientX, left: scroller.scrollLeft, moved: false };
  });
  window.addEventListener("pointermove", (e) => {
    if (!drag) return;
    const dx = e.clientX - drag.x;
    if (Math.abs(dx) > 5) {
      drag.moved = true;
      scroller.classList.add("dragging");
    }
    if (drag.moved) scroller.scrollLeft = drag.left - dx;
  });
  window.addEventListener("pointerup", () => {
    if (!drag) return;
    if (drag.moved) {
      suppressClick = true;
      setTimeout(() => (suppressClick = false), 60);
    }
    drag = null;
    scroller.classList.remove("dragging");
  });

  track.addEventListener("click", (e) => {
    if (suppressClick) return;
    const g = e.target.closest(".garment");
    if (g) selectItem(Number(g.dataset.id));
  });

  track.addEventListener("keydown", (e) => {
    const list = [...track.querySelectorAll(".garment")];
    const i = list.indexOf(document.activeElement);
    if (i === -1) return;
    if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
      e.preventDefault();
      const next = list[Math.min(list.length - 1, Math.max(0, i + (e.key === "ArrowRight" ? 1 : -1)))];
      next.focus({ preventScroll: true });
      const left = next.offsetLeft - (scroller.clientWidth - next.offsetWidth) / 2;
      scroller.scrollTo({ left: Math.max(0, left), behavior: "smooth" });
    }
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && state.activeId != null) clearSelection();
  });

  /* ------------------------------------------------------------------ seleção + painel */
  async function selectItem(id) {
    const item = state.items.find((i) => i.id === id);
    if (!item) return;

    state.activeId = id;
    state.trackIndex = 0;
    state.detail = null;
    const token = ++state.token;

    updateFocus();
    centerOn(id);
    stopAudio();
    renderItemInfo(item);
    renderTrackChips([]);
    renderTrack(null, { loading: true });

    panelEmpty.classList.add("hidden");
    panelContent.classList.remove("hidden");
    panelContent.classList.add("grid");
    if (window.matchMedia("(max-width: 1023px)").matches) {
      panelContent.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }

    try {
      const detail = await getDetail(id);
      if (token !== state.token) return;
      state.detail = detail;
      renderItemInfo(detail);
      showTrack(0, { autoplay: true });
    } catch (err) {
      console.error(err);
      if (token !== state.token) return;
      renderTrack(null, { error: "Não foi possível carregar a música agora. Tente de novo em instantes." });
    }
  }

  function clearSelection() {
    state.token++;
    state.activeId = null;
    state.detail = null;
    stopAudio();
    panelContent.classList.add("hidden");
    panelContent.classList.remove("grid");
    panelEmpty.classList.remove("hidden");
    updateFocus();
  }

  function renderItemInfo(item) {
    const style = $("#p-style");
    style.textContent = item.style;
    style.className = `badge badge-${item.style}`;
    $("#p-name").textContent = item.name;
    $("#p-brand").textContent = item.brand;
    $("#p-category").textContent = item.category;
    $("#p-details").textContent = item.details;
    const thumb = $("#p-thumb");
    const src = assetUrl(item.image_file);
    thumb.alt = item.name;
    if (src) {
      thumb.style.visibility = "visible";
      thumb.src = src;
    } else {
      thumb.removeAttribute("src");
      thumb.style.visibility = "hidden";
    }
  }

  function renderTrackChips(tracks) {
    const box = $("#t-chips");
    box.replaceChildren();
    if (tracks.length < 2) return;
    tracks.forEach((t, i) => {
      box.append(el("button", {
        type: "button",
        class: "track-chip",
        "aria-pressed": String(i === state.trackIndex),
        onclick: () => showTrack(i, { autoplay: true }),
      }, `${t.title || t.artist} — ${t.artist}`));
    });
  }

  function showTrack(index, { autoplay = false } = {}) {
    const tracks = (state.detail && state.detail.tracks) || [];
    const t = tracks[index];
    state.trackIndex = index;
    renderTrackChips(tracks);
    if (!t) {
      renderTrack(null, { error: "Esta peça ainda não tem música associada." });
      return;
    }
    renderTrack(t, {});
    if (t.preview_url) {
      audio.src = t.preview_url;
      audio.load();
      if (autoplay) audio.play().catch(() => setPlayingUI(false)); // o navegador pode bloquear
    }
  }

  function renderTrack(t, { loading = false, error = "" } = {}) {
    const cover = $("#cover-img");
    const fallback = $("#cover-fallback");
    const link = $("#t-link");
    const note = $("#t-note");
    const playBtn = $("#btn-play");
    const seek = $("#seek");

    stopAudio();
    seek.value = 0;
    $("#t-cur").textContent = "0:00";
    $("#t-dur").textContent = "0:30";

    if (!t) {
      $("#t-title").textContent = loading ? "Carregando…" : "Sem música";
      $("#t-artist").textContent = "";
      $("#t-album").textContent = "";
      cover.classList.add("hidden");
      fallback.classList.remove("hidden");
      link.classList.add("hidden");
      note.textContent = error;
      playBtn.disabled = true;
      seek.disabled = true;
      return;
    }

    $("#t-title").textContent = t.title || t.artist;
    $("#t-artist").textContent = t.artist;
    $("#t-album").textContent = t.album || "";

    if (t.cover_url) {
      cover.onerror = () => {
        cover.classList.add("hidden");
        fallback.classList.remove("hidden");
      };
      cover.src = t.cover_url;
      cover.alt = `Capa: ${t.album || t.title || t.artist}`;
      cover.classList.remove("hidden");
      fallback.classList.add("hidden");
    } else {
      cover.classList.add("hidden");
      fallback.classList.remove("hidden");
    }

    if (t.spotify_url) {
      link.href = t.spotify_url;
      link.classList.remove("hidden");
    } else {
      link.classList.add("hidden");
    }

    const hasPreview = Boolean(t.preview_url);
    playBtn.disabled = !hasPreview;
    seek.disabled = !hasPreview;
    if (!hasPreview) {
      note.textContent = t.spotify_url
        ? "Prévia indisponível para esta faixa — abra no Spotify para ouvir."
        : "Prévia e capa indisponíveis no momento (verifique as credenciais do Spotify).";
    } else {
      note.textContent = t.preview_source === "itunes" ? "Prévia de 30 s via iTunes." : "Prévia de 30 s via Spotify.";
    }
  }

  /* ------------------------------------------------------------------ player */
  function setPlayingUI(playing) {
    playerEl.classList.toggle("playing", playing);
    $("#icon-play").classList.toggle("hidden", playing);
    $("#icon-pause").classList.toggle("hidden", !playing);
    $("#btn-play").setAttribute("aria-label", playing ? "Pausar" : "Tocar");
  }

  function stopAudio() {
    audio.pause();
    audio.removeAttribute("src");
    audio.load();
    setPlayingUI(false);
  }

  $("#btn-play").addEventListener("click", () => {
    if (!audio.src) return;
    if (audio.paused) audio.play().catch(() => setPlayingUI(false));
    else audio.pause();
  });

  audio.addEventListener("play", () => setPlayingUI(true));
  audio.addEventListener("pause", () => setPlayingUI(false));
  audio.addEventListener("ended", () => {
    setPlayingUI(false);
    $("#seek").value = 0;
    $("#t-cur").textContent = "0:00";
  });
  audio.addEventListener("loadedmetadata", () => {
    if (Number.isFinite(audio.duration)) $("#t-dur").textContent = fmtTime(audio.duration);
  });
  audio.addEventListener("timeupdate", () => {
    if (!audio.duration) return;
    if (!seeking) $("#seek").value = Math.round((audio.currentTime / audio.duration) * 1000);
    $("#t-cur").textContent = fmtTime(audio.currentTime);
  });
  audio.addEventListener("error", () => {
    if (!audio.getAttribute("src")) return;
    setPlayingUI(false);
    $("#t-note").textContent = "Não foi possível tocar esta prévia.";
  });

  let seeking = false;
  const seekEl = $("#seek");
  seekEl.addEventListener("pointerdown", () => (seeking = true));
  window.addEventListener("pointerup", () => (seeking = false));
  seekEl.addEventListener("input", () => {
    if (audio.duration) audio.currentTime = (seekEl.value / 1000) * audio.duration;
  });

  const volEl = $("#volume");
  try {
    const saved = localStorage.getItem("soundrack:volume");
    if (saved !== null) volEl.value = saved;
  } catch (_) { /* armazenamento indisponível */ }
  audio.volume = volEl.value / 100;
  volEl.addEventListener("input", () => {
    audio.volume = volEl.value / 100;
    try { localStorage.setItem("soundrack:volume", volEl.value); } catch (_) { /* ignora */ }
  });

  /* ------------------------------------------------------------------ arranque */
  async function init() {
    try {
      const [items, styles] = await Promise.all([fetchJSON(`${API}/items`), fetchJSON(`${API}/styles`)]);
      state.items = items;
      state.styles = styles;
      renderFilters();
      renderRack();
    } catch (err) {
      console.error(err);
      statusEl.textContent = "Não consegui carregar a arara. O servidor FastAPI está a correr?";
      statusEl.classList.add("text-blood");
    }
  }

  init();
})();
