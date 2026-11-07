const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (t) => String(t ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const media = (p) => `/media?p=${encodeURIComponent(p)}`;
let LIB = { personagens: [], fundos: [], musicas: [], vozes: {} };
let BATCH = null;
let CANAIS = [];  // channels: each has its own Drive folder; batches are shown and sent per channel
let CANAL = (() => { try { return localStorage.getItem("canal") || ""; } catch { return ""; } })();
const canalDe = (b) => b.canal || "principal";
const canalNome = (id) => CANAIS.find((c) => c.id === id)?.nome || "canal removido";

async function api(url, opts = {}) {
  const r = await fetch(url, opts);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.erro || `Erro ${r.status}`);
  return data;
}
function savedFlash(box) {  // the checkboxes save on click: show it next to "Escolher ..."
  const sum = $("summary", box.closest("details"));
  let tag = $(".salvo", sum);
  if (!tag) { tag = document.createElement("span"); tag.className = "salvo"; sum.append(tag); }
  tag.textContent = " ✓ salvo";
  clearTimeout(tag.timer);
  tag.timer = setTimeout(() => (tag.textContent = ""), 2000);
}
const json = (method, body) => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

// ------------------------------------------------------------------ tabs
function showTab(name) {
  $$(".tabs button").forEach((b) => b.classList.toggle("on", b.dataset.tab === name));
  $$(".tab").forEach((t) => t.classList.toggle("on", t.id === `tab-${name}`));
  if (name === "fila") loadQueue();
}
$$(".tabs button").forEach((b) => (b.onclick = () => showTab(b.dataset.tab)));

// ------------------------------------------------------------------ library
async function loadLib() {
  LIB = await api("/api/biblioteca");
  const bgOptions = LIB.fundos.map((f) => `<option value="${f.id}">${esc(f.nome)}</option>`).join("");
  $$(".sel-fundos").forEach((s) => (s.innerHTML = bgOptions));
  $("#sel-vozes").innerHTML = Object.entries(LIB.vozes).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join("");
  $("#sel-temas").innerHTML = Object.entries(LIB.temas || {}).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join("");
  $("#dl-nichos").innerHTML = [...new Set(LIB.personagens.map((c) => c.nicho).filter(Boolean))].sort().map((n) => `<option value="${esc(n)}">`).join("");
  renderCharacters();
  renderMedia();
  if (BATCH) renderBatch(BATCH);
}

function renderCharacters() {
  const nichos = {};
  LIB.personagens.forEach((c) => (nichos[c.nicho || "Sem nicho"] = (nichos[c.nicho || "Sem nicho"] || 0) + 1));
  const sel = $("#f-nicho"), cur = sel.value;
  sel.innerHTML = `<option value="">Todos os nichos (${LIB.personagens.length})</option>` + Object.keys(nichos).sort()
    .map((n) => `<option value="${esc(n)}" ${n === cur ? "selected" : ""}>${esc(n)} (${nichos[n]})</option>`).join("");
  const q = norm($("#f-busca").value);
  const list = LIB.personagens.filter((c) => (!sel.value || (c.nicho || "Sem nicho") === sel.value)
    && (!q || norm([c.nome, ...c.aliases, c.categoria, c.especialidades].join(" ")).includes(q)));
  const groups = {};
  list.forEach((c) => (groups[c.nicho || "Sem nicho"] ||= []).push(c));
  const bgName = (id) => LIB.fundos.find((f) => f.id === id)?.nome || id;
  const musChips = (ids) => ids.map((m) => `<button type="button" class="chip" data-ouvir="${m}" title="Ouvir">▶ ${esc(LIB.musicas.find((x) => x.id === m)?.nome || m)}</button>`).join("")
    || '<span class="muted small">Sem música</span>';
  const card = (c) => {
    const fundos = c.fundos?.length ? c.fundos : [c.fundo];
    const imgs = c.imagens?.length ? c.imagens : [c.imagem];
    return `<div class="card char">
      <div class="checker"><img src="${media(c.imagem)}" alt="${esc(c.nome)}" loading="lazy"></div>
      <h3 class="nome-h">${esc(c.nome)} <button type="button" class="link small" data-edit="${c.id}" title="Editar nome e dados">✎ editar</button></h3>
      <form class="edit-form hide" data-cid="${c.id}">
        <label class="small">Nome<input name="nome" value="${esc(c.nome)}" required></label>
        <label class="small">Outros nomes no roteiro (separados por vírgula)<input name="aliases" value="${esc((c.aliases || []).join(", "))}"></label>
        <label class="small">Nicho<input name="nicho" list="dl-nichos" value="${esc(c.nicho || "")}"></label>
        <label class="small">Categoria<input name="categoria" value="${esc(c.categoria || "")}"></label>
        <label class="small">Especialidades<input name="especialidades" value="${esc(c.especialidades || "")}"></label>
        <div class="small edit-msg"></div>
        <button class="btn small">Salvar</button> <button type="button" class="btn ghost small" data-cancel>Cancelar</button>
      </form>
      <div class="meta">${c.categoria ? esc(c.categoria) + "<br>" : ""}${c.especialidades ? `<span class="tags">${esc(c.especialidades)}</span><br>` : ""}
        ${c.imagem_provisoria ? '<span style="color:var(--warn)">Imagem provisória: envie o PNG sem fundo.</span>'
          : !c.transparente ? '<span style="color:var(--warn)">Imagem com fundo: não foi possível remover. Envie um PNG sem fundo.</span>'
          : c.fundo_removido ? '<span style="color:var(--ok)">Fundo removido automaticamente.</span>' : ""}</div>
      <label class="btn ghost small">${c.imagem_provisoria ? "Enviar imagem" : "Trocar imagem"}<input type="file"
        accept="image/png,image/webp" data-img="${c.id}" hidden></label>
      ${c.imagem_provisoria ? "" : `<div class="sub-h">Imagens (rodízio a cada vídeo)</div>
      ${imgs.length > 1 ? `<div class="img-rod">${imgs.map((p) => `<div class="checker"><img src="${media(p)}" alt="" loading="lazy">
        <button type="button" class="x-mini" data-rmimg="${esc(p)}" data-cid="${c.id}" title="Tirar do rodízio">×</button></div>`).join("")}</div>` : ""}
      <label class="btn ghost small">+ Adicionar imagem<input type="file" accept="image/*" data-addimg="${c.id}" hidden></label>
      <div class="small muted img-msg">${imgs.length > 1 ? `${imgs.length} imagens: cada vídeo usa a próxima.` : "Só uma imagem: ela aparece em todos os vídeos."}</div>`}
      <div class="sub-h">Voz</div>
      ${c.voz.motor === "chatterbox" ? '<div class="meta">Clonada de gravação</div>'
        : `<select data-cid="${c.id}" data-field="voz">${Object.entries(LIB.vozes).map(([k, v]) =>
          `<option value="${esc(k)}" ${k === c.voz.voz ? "selected" : ""}>${esc(v)}</option>`).join("")}</select>`}
      ${c.amostra_voz ? `<audio src="${media(c.amostra_voz)}" controls preload="none"></audio>` : ""}
      <details class="nova-voz"><summary>Usar outra gravação (arquivo ou vídeo)</summary>
        <input class="nv-url" placeholder="Link do vídeo (YouTube etc.)">
        <div class="rc-tempos"><label>Início<input class="nv-ini" placeholder="3:00"></label>
          <label>Fim<input class="nv-fim" placeholder="3:30"></label>
          <button type="button" class="btn small nv-cortar">Recortar</button></div>
        <div class="small muted nv-msg">20 a 30 s de fala limpa, sem música.</div>
        <audio class="nv-audio hide" controls></audio>
        <div class="small muted">ou arquivo de áudio:</div><input type="file" class="nv-arq" accept="audio/*">
        <label class="inline small"><input type="checkbox" class="nv-aut"> Esta é a minha voz ou tenho autorização do
          dono desta voz para clonar.</label>
        <button type="button" class="btn small nv-salvar" data-cid="${c.id}">Salvar voz</button>
      </details>
      <div class="sub-h">Fundos (rodízio a cada vídeo)</div>
      <div class="chips-mini">${fundos.map((f) => `<span class="chip">${esc(bgName(f))}</span>`).join("")}</div>
      <details><summary>Escolher fundos</summary><div class="bg-checks" data-cid="${c.id}">${LIB.fundos.map((f) =>
        `<label class="inline small"><input type="checkbox" value="${f.id}" ${fundos.includes(f.id) ? "checked" : ""}> ${esc(f.nome)}</label>`).join("")}</div></details>
      <div class="sub-h">Músicas (rodízio a cada vídeo)</div>
      <div class="chips-mini mus-chips">${musChips(c.musicas || [])}</div>
      <details><summary>Escolher músicas</summary><div class="mus-checks bg-checks" data-cid="${c.id}">${LIB.musicas.map((m) =>
        `<label class="inline small"><input type="checkbox" value="${m.id}" ${(c.musicas || []).includes(m.id) ? "checked" : ""}> ${esc(m.nome)}</label>`).join("")}</div></details>
      <label class="small">Lado<select data-cid="${c.id}" data-field="lado">
        <option value="esquerda" ${c.lado === "esquerda" ? "selected" : ""}>Esquerda</option>
        <option value="direita" ${c.lado === "direita" ? "selected" : ""}>Direita</option></select></label>
      <button class="btn danger small" style="margin-top:10px" data-del="${c.id}">Remover</button>
    </div>`;
  };
  $("#lista-personagens").innerHTML = Object.keys(groups).sort().map((g) =>
    `<h2 class="grupo">${esc(g)} <span class="muted small">${groups[g].length}</span></h2><div class="cards">${groups[g].map(card).join("")}</div>`).join("")
    || '<p class="muted">Nenhum personagem encontrado.</p>';
  const after = async () => {
    await loadLib();
    if (BATCH) BATCH = await api(`/api/lotes/${BATCH.id}/reanalisar`, { method: "POST" }), renderBatch(BATCH);
  };
  $$("#lista-personagens select[data-field]").forEach((s) => (s.onchange = async () => {
    await api(`/api/personagens/${s.dataset.cid}`, json("PATCH", { [s.dataset.field]: s.value }));
    loadLib();
  }));
  $$("#lista-personagens [data-edit]").forEach((btn) => (btn.onclick = () =>
    $(".edit-form", btn.closest(".char")).classList.toggle("hide")));
  $$("#lista-personagens .edit-form").forEach((f) => {
    $("[data-cancel]", f).onclick = () => f.classList.add("hide");
    f.onsubmit = async (e) => {
      e.preventDefault();
      const d = Object.fromEntries(new FormData(f));
      d.aliases = d.aliases.split(",");
      try { await api(`/api/personagens/${f.dataset.cid}`, json("PATCH", d)); after(); }
      catch (err) { $(".edit-msg", f).innerHTML = `<span style="color:var(--bad)">${esc(err.message)}</span>`; }
    };
  });
  $$("#lista-personagens .mus-checks input").forEach((cb) => (cb.onchange = async () => {
    const box = cb.closest(".mus-checks");
    const ids = $$("input:checked", box).map((x) => x.value);
    try { await api(`/api/personagens/${box.dataset.cid}`, json("PATCH", { musicas: ids })); }
    catch (err) { cb.checked = !cb.checked; return alert(`Não salvou: ${err.message}`); }
    savedFlash(box);
    $(".mus-chips", box.closest(".char")).innerHTML = musChips(ids);
    LIB.personagens.find((c) => c.id === box.dataset.cid).musicas = ids;
  }));
  $("#lista-personagens").onclick = (e) => {
    const btn = e.target.closest("[data-ouvir]");
    if (!btn) return;
    const m = LIB.musicas.find((x) => x.id === btn.dataset.ouvir);
    if (PLAYER.dataset.id === m.id && !PLAYER.paused) return PLAYER.pause();
    PLAYER.src = media(m.arquivo);
    PLAYER.dataset.id = m.id;
    PLAYER.play();
  };
  $$("#lista-personagens .bg-checks:not(.mus-checks) input").forEach((cb) => (cb.onchange = async () => {
    const box = cb.closest(".bg-checks");
    const ids = $$("input:checked", box).map((x) => x.value);
    if (!ids.length) return (cb.checked = true);
    try { await api(`/api/personagens/${box.dataset.cid}`, json("PATCH", { fundos: ids })); }
    catch (err) { cb.checked = !cb.checked; return alert(`Não salvou: ${err.message}`); }
    savedFlash(box);
    $(".chips-mini", box.closest(".char")).innerHTML = ids.map((f) => `<span class="chip">${esc(bgName(f))}</span>`).join("");
    LIB.personagens.find((c) => c.id === box.dataset.cid).fundos = ids;
  }));
  $$("#lista-personagens [data-img]").forEach((inp) => (inp.onchange = async () => {
    const fd = new FormData();
    fd.append("imagem", inp.files[0]);
    inp.parentElement.firstChild.textContent = "Verificando fundo… (se tiver, a remoção leva ~30 s)";
    try { await api(`/api/personagens/${inp.dataset.img}/imagem`, { method: "POST", body: fd }); }
    catch (err) { alert(err.message); }
    after();
  }));
  $$("#lista-personagens [data-addimg]").forEach((inp) => (inp.onchange = async () => {
    const fd = new FormData();
    fd.append("imagem", inp.files[0]);
    $(".img-msg", inp.closest(".char")).textContent = "Verificando fundo… (se tiver, a remoção leva ~30 s)";
    try { await api(`/api/personagens/${inp.dataset.addimg}/imagens`, { method: "POST", body: fd }); }
    catch (err) { alert(err.message); }
    after();
  }));
  $$("#lista-personagens [data-rmimg]").forEach((b) => (b.onclick = async () => {
    if (!confirm("Tirar esta imagem do rodízio?")) return;
    try { await api(`/api/personagens/${b.dataset.cid}/imagens`, json("DELETE", { caminho: b.dataset.rmimg })); }
    catch (err) { alert(err.message); }
    after();
  }));
  $$("#lista-personagens .nova-voz").forEach((box) => {
    let clipId = "";
    $(".nv-cortar", box).onclick = async () => {
      const msg = $(".nv-msg", box);
      msg.textContent = "Baixando só o trecho escolhido...";
      try {
        const r = await api("/api/recortar-voz", json("POST", { url: $(".nv-url", box).value, inicio: $(".nv-ini", box).value, fim: $(".nv-fim", box).value }));
        clipId = r.id;
        $(".nv-audio", box).src = media(r.arquivo);
        $(".nv-audio", box).classList.remove("hide");
        msg.innerHTML = `<span style="color:var(--ok)">Trecho de ${r.duracao} s recortado.</span> Ouça antes de salvar.`;
      } catch (err) { msg.innerHTML = `<span style="color:var(--bad)">${esc(err.message)}</span>`; }
    };
    $(".nv-salvar", box).onclick = async () => {
      const fd = new FormData(), file = $(".nv-arq", box).files[0];
      if (file) fd.append("voz_arquivo", file);
      fd.append("voz_recorte", clipId);
      if ($(".nv-aut", box).checked) fd.append("autorizacao", "sim");
      try { await api(`/api/personagens/${$(".nv-salvar", box).dataset.cid}/voz`, { method: "POST", body: fd }); after(); }
      catch (err) { $(".nv-msg", box).innerHTML = `<span style="color:var(--bad)">${esc(err.message)}</span>`; }
    };
  });
  $$("#lista-personagens [data-del]").forEach((b) => (b.onclick = async () => {
    if (!confirm("Remover este personagem?")) return;
    await api(`/api/personagens/${b.dataset.del}`, { method: "DELETE" });
    loadLib();
  }));
}
const PLAYER = new Audio();
const norm = (t) => String(t || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
$("#f-nicho").onchange = renderCharacters;
$("#f-busca").oninput = renderCharacters;

function renderMedia() {
  const card = (kind, m, player) => `<div class="card media">${player}<h3 style="margin:8px 0 2px">${esc(m.nome)}</h3>
    <div class="muted small">${esc(m.origem)}</div>
    ${m.temas?.length ? `<div class="chips-mini">${m.temas.map((t) => `<span class="chip">${esc(LIB.temas[t] || t)}</span>`).join("")}</div>` : ""}
    <button class="btn danger small" style="margin-top:8px" data-kind="${kind}" data-del="${m.id}">Remover</button></div>`;
  $("#lista-fundos").innerHTML = LIB.fundos.map((f) => card("fundos", f,
    `<video src="${media(f.arquivo)}" muted loop playsinline preload="metadata" onmouseenter="this.play()" onmouseleave="this.pause()"></video>`)).join("")
    || '<p class="muted">Nenhum fundo.</p>';
  $("#lista-musicas").innerHTML = LIB.musicas.map((m) => card("musicas", m, `<audio src="${media(m.arquivo)}" controls preload="none"></audio>`)).join("")
    || '<p class="muted">Nenhuma música ainda. Adicione músicas com licença conhecida.</p>';
  $$("#tab-midias [data-del]").forEach((b) => (b.onclick = async () => {
    if (!confirm("Remover?")) return;
    await api(`/api/${b.dataset.kind}/${b.dataset.del}`, { method: "DELETE" });
    loadLib();
  }));
}

// ------------------------------------------------------------------ new character form
const form = $("#form-personagem");
form.voz_tipo.forEach((r) => (r.onchange = () => {
  const clone = form.voz_tipo.value === "clonar";
  $("#voz-clonar").classList.toggle("hide", !clone);
  $("#voz-pronta").classList.toggle("hide", clone);
}));
form.imagem.onchange = () => {
  const file = form.imagem.files[0];
  if (!file) return;
  const img = $("#prev-img");
  img.src = URL.createObjectURL(file);
  $("#prev-wrap").classList.remove("hide");
  $("#prev-wrap").classList.add("checker");
  img.onload = () => {  // check for transparent pixels
    const c = document.createElement("canvas");
    c.width = 120; c.height = Math.round((120 * img.naturalHeight) / img.naturalWidth);
    const ctx = c.getContext("2d");
    ctx.drawImage(img, 0, 0, c.width, c.height);
    const a = ctx.getImageData(0, 0, c.width, c.height).data;
    let transparent = 0;
    for (let i = 3; i < a.length; i += 4) if (a[i] < 250) transparent++;
    $("#prev-msg").innerHTML = transparent > a.length / 40
      ? '<span style="color:var(--ok)">Fundo transparente OK.</span>'
      : '<span style="color:var(--warn)">Esta imagem parece ter fundo. Use um PNG recortado (sem fundo).</span>';
  };
};
$("#rc-btn").onclick = async () => {
  const msg = $("#rc-msg"), btn = $("#rc-btn");
  btn.disabled = true;
  $("#rc-id").value = "";
  $("#rc-audio").classList.add("hide");
  msg.innerHTML = "Baixando só o trecho escolhido... (pode levar até 1 minuto)";
  try {
    const r = await api("/api/recortar-voz", json("POST", { url: $("#rc-url").value, inicio: $("#rc-ini").value, fim: $("#rc-fim").value }));
    $("#rc-id").value = r.id;
    $("#rc-audio").src = media(r.arquivo);
    $("#rc-audio").classList.remove("hide");
    msg.innerHTML = `<span style="color:var(--ok)">Trecho de ${r.duracao} s recortado de "${esc(r.titulo)}".</span>
      Ouça abaixo; se tiver música ou outra pessoa falando, ajuste os tempos e recorte de novo.`;
  } catch (err) {
    msg.innerHTML = `<span style="color:var(--bad)">${esc(err.message)}</span>`;
  }
  btn.disabled = false;
};
form.onsubmit = async (e) => {
  e.preventDefault();
  const msg = $("#form-personagem-msg");
  msg.textContent = "Salvando... (se a imagem tiver fundo, a remoção leva ~30 s)";
  try {
    const c = await api("/api/personagens", { method: "POST", body: new FormData(form) });
    msg.innerHTML = `<span style="color:var(--ok)">${esc(c.nome)} cadastrado.${c.fundo_removido ? " Fundo da imagem removido automaticamente." : ""}</span>`;
    form.reset();
    $("#prev-wrap").classList.add("hide");
    $("#rc-audio").classList.add("hide");
    $("#rc-id").value = "";
    await loadLib();
    if (BATCH) BATCH = await api(`/api/lotes/${BATCH.id}/reanalisar`, { method: "POST" }), renderBatch(BATCH);
  } catch (err) {
    msg.innerHTML = `<span style="color:var(--bad)">${esc(err.message)}</span>`;
  }
};

$$(".media-form").forEach((f) => (f.onsubmit = async (e) => {
  e.preventDefault();
  const msg = $(".msg", f);
  msg.textContent = "Enviando...";
  try {
    await api(`/api/${f.dataset.kind}`, { method: "POST", body: new FormData(f) });
    msg.innerHTML = '<span style="color:var(--ok)">Adicionado.</span>';
    f.reset();
    loadLib();
  } catch (err) {
    msg.innerHTML = `<span style="color:var(--bad)">${esc(err.message)}</span>`;
  }
}));

// ------------------------------------------------------------------ upload PDFs
const drop = $("#drop");
["dragenter", "dragover"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("over"); }));
["dragleave", "drop"].forEach((ev) => drop.addEventListener(ev, () => drop.classList.remove("over")));

function walk(entry, out) {  // read dropped folders recursively, keeping relative paths
  return new Promise((resolve) => {
    if (entry.isFile) entry.file((f) => { out.push({ file: f, path: entry.fullPath.replace(/^\//, "") }); resolve(); });
    else if (entry.isDirectory) {
      const reader = entry.createReader(), all = [];
      const read = () => reader.readEntries(async (batch) => {
        if (!batch.length) { await Promise.all(all.map((x) => walk(x, out))); resolve(); }
        else { all.push(...batch); read(); }
      });
      read();
    } else resolve();
  });
}
drop.addEventListener("drop", async (e) => {
  e.preventDefault();
  const out = [];
  await Promise.all([...e.dataTransfer.items].map((it) => it.webkitGetAsEntry()).filter(Boolean).map((en) => walk(en, out)));
  upload(out);
});
function colado(raw) {  // pasted text -> a .txt item; a second paste with the same title gets _2, _3... (never replaces)
  const text = raw.replace(/^\s*```\w*\s*$/gm, "").trim();  // tolerate pasted code fences
  if (!text) return null;
  const title = (text.match(/^T[ÍI]TULO[^:]*:\s*(.+)$/im) || [, "roteiro"])[1];
  const base = title.normalize("NFD").replace(/[^\w\s-]/g, "").trim().replace(/\s+/g, "_").slice(0, 50) || "roteiro";
  const used = new Set((BATCH ? ITENS : []).map((x) => x.path));
  let name = `${base}.txt`;
  for (let i = 2; used.has(name); i++) name = `${base}_${i}.txt`;
  return { file: new File([text], name, { type: "text/plain" }), path: name };
}
$("#btn-colar").onclick = async () => {
  const item = colado($("#txt-roteiro").value);
  if (!item) return $("#txt-roteiro").focus();
  if (await upload([item])) $("#txt-roteiro").value = "";  // read: the box is empty for the next one
};

// "+ Adicionar roteiro": a popup over the list to paste (or pick) one more script into the same list
function abrirAdd() {
  const d = MODO === "trad" ? DROP.trad : DROP[TEMPLATE];
  $("#add-lbl-files").classList.toggle("hide", !d.arquivos);
  $("#add-lbl-folder").classList.toggle("hide", !d.pasta);
  $("#add-texto").classList.toggle("hide", !d.colar);
  $("#add-msg").textContent = d.colar ? "" : "Personagem falando: escolha a pasta do episódio (roteiro + imagens).";
  $("#add-texto").value = "";
  $("#modal-add").classList.remove("hide");
  if (d.colar) $("#add-texto").focus();
}
const fecharAdd = () => $("#modal-add").classList.add("hide");
async function adicionar(items) {
  $("#add-msg").textContent = "Lendo…";
  if (await upload(items)) { fecharAdd(); $("#add-texto").value = ""; }
  else $("#add-msg").innerHTML = $("#drop-status").innerHTML;
}
$("#btn-add").onclick = abrirAdd;
$("#add-fechar-x").onclick = fecharAdd;
$("#modal-add").onclick = (e) => { if (e.target.id === "modal-add") fecharAdd(); };
$("#add-enviar").onclick = () => {
  const item = colado($("#add-texto").value);
  if (!item) return $("#add-texto").focus();
  adicionar([item]);
};
$("#add-files").onchange = (e) => { adicionar([...e.target.files].map((f) => ({ file: f, path: f.name }))); e.target.value = ""; };
$("#add-folder").onchange = (e) => {
  adicionar([...e.target.files].map((f) => ({ file: f, path: f.webkitRelativePath || f.name }))); e.target.value = "";
};
$("#in-files").onchange = (e) => upload([...e.target.files].map((f) => ({ file: f, path: f.name })));
$("#in-folder").onchange = (e) => upload([...e.target.files].map((f) => ({ file: f, path: f.webkitRelativePath || f.name })));

let ITENS = [];  // everything picked since the last start/clear: each new pick is added to the same list
async function upload(items) {
  items = items.filter((x) => /\.(txt|md|pdf|png|jpe?g|webp)$/i.test(x.path));
  if (!items.length) return ($("#drop-status").textContent = "Nenhum roteiro (.txt, .md, .pdf) ou imagem encontrado.");
  const old = BATCH?.id;
  if (old) {  // a list is open and not started yet: add to it (a file picked again replaces its old copy)
    const novos = new Set(items.map((x) => x.path));
    items = [...ITENS.filter((x) => !novos.has(x.path)), ...items];
  }
  const fd = new FormData();
  items.forEach((x) => fd.append("arquivos", x.file, x.path));
  fd.append("canal", CANAL);
  $("#drop-status").textContent = `Lendo ${items.filter((x) => /\.(txt|md|pdf)$/i.test(x.path)).length} roteiro(s)...`;
  try {
    BATCH = await api("/api/lotes", { method: "POST", body: fd });
    ITENS = items;
    if (old) api(`/api/lotes/${old}`, { method: "DELETE" }).catch(() => {});  // the merged list replaced it
    $("#drop-status").textContent = "";
    renderBatch(BATCH);
    abrirLote();
    return true;
  } catch (err) {
    $("#drop-status").innerHTML = `<span style="color:var(--bad)">${esc(err.message)}</span>`;
    return false;
  } finally {
    $("#in-files").value = $("#in-folder").value = "";
  }
}

// ------------------------------------------------------------------ batch review
// same template + same scenes (speaker/mode and text) = the same video
const assinatura = (v) => `${v.template}|${JSON.stringify((v.cenas || []).map((c) => [c.personagem || c.mode || "", c.text]))}`;
let FILA_SIGS = new Map();  // signature -> title, for the videos queued or rendering now (filled by loadQueue)

function renderBatch(b) {  // refreshes the popup; upload() is what opens it
  const vistos = new Set();
  const count = (t) => b.videos.filter((v) => v.template === t).length;
  const ok = b.videos.filter((v) => v.pronto_para_gerar).length;
  $("#resumo").innerHTML = `<span class="chip">${b.videos.length} roteiro(s)</span>
    ${count("F01") ? `<span class="chip t01">${count("F01")} Personagem falando</span>` : ""}
    ${count("T02") ? `<span class="chip t02">${count("T02")} Entrevista</span>` : ""}
    <span class="chip ok">${ok} prontos</span>${ok < b.videos.length ? `<span class="chip bad">${b.videos.length - ok} com pendência</span>` : ""}`;
  $("#lote-rows").innerHTML = b.videos.map((v) => {
    const people = v.template === "T02"
      ? v.personagens.map((p) => v.personagens_status?.[p]
          ? `<span class="chip ok">${esc(p)}</span>`
          : `<span class="chip bad">${esc(p)}</span> <button class="link" data-cadastrar="${esc(p)}">cadastrar</button>`).join(" ")
      : `${esc(v.personagens.join(", "))}<div class="muted small">Imagens: ${esc(v.imagens_resumo || `${v.imagens.filter(Boolean).length}/${v.cenas.length} ${v.origem_imagens}`)}</div>`;
    const tag = v.template === "F01" ? '<span class="chip t01">Personagem falando</span>'
      : v.template === "T02" ? '<span class="chip t02">Entrevista</span>' : '<span class="chip bad">Desconhecido</span>';
    const lang = v.idioma ? `<span class="chip">${v.idioma === "en" ? "Inglês" : "Português"}</span>` : "";
    const status = v.pronto_para_gerar ? '<span class="chip ok">Pronto</span>'
      : `<ul class="problems">${v.problemas.map((p) => `<li>${esc(p)}</li>`).join("")}</ul>`
        + (v.fotos_faltando || []).map((c) => `<label class="btn small foto-falta">📷 Enviar foto de ${esc(c.nome)}<input
            type="file" accept="image/*" data-fotofalta="${esc(c.id)}" hidden></label>`).join("");
    const anim = (v.animacoes_total ? `<div><span class="chip anim" title="Animações marcadas no roteiro (Smart Motion)">🎬 ${v.animacoes_total} animaç${v.animacoes_total > 1 ? "ões" : "ão"}</span></div>` : "")
      + ((v.avisos_animacao || []).length ? `<ul class="avisos">${v.avisos_animacao.map((p) => `<li>${esc(p)}</li>`).join("")}</ul>` : "");
    const fora = MODO === "placa" && v.template && v.template !== TEMPLATE;  // not the template chosen on the board
    const sig = assinatura(v);
    const naFila = v.cenas?.length && FILA_SIGS.has(sig), repetido = v.cenas?.length && vistos.has(sig);
    vistos.add(sig);
    const dup = naFila || repetido;  // left unchecked: tick it to make it anyway
    return `<tr class="${v.pronto_para_gerar && !dup ? "" : "blocked"}"><td><input type="checkbox" class="chk" value="${v.id}"
      ${v.pronto_para_gerar ? (fora || dup ? "" : "checked") : "disabled"}></td><td>${esc(v.arquivo)}</td><td>${tag} ${lang}
      ${fora ? '<div><span class="chip fora" title="Marque o template no painel, ou marque esta linha para gerar mesmo assim">template não escolhido</span></div>' : ""}
      ${dup ? `<div><span class="chip bad" title="Mesmo texto e mesmas cenas. Ficou desmarcado; marque a linha só se quiser gerar de novo.">${naFila
        ? "duplicado: já está na fila" : "duplicado: repetido nesta lista"}</span></div>` : ""}</td>
      <td><b>${esc(v.titulo)}</b><div class="muted small">${esc(v.subtitulo)}</div>
        ${v.serie ? `<div><span class="chip t02 serie" title="Capa de série: o nome da série e o episódio aparecem na capa">📺 ${esc(v.serie)} · ${esc(v.episodio_txt || "")}</span></div>`
          : '<div class="muted small">Vídeo avulso (capa normal)</div>'}</td><td>${v.cenas.length}</td>
      <td>${people}</td><td>${status}${anim}</td></tr>`;
  }).join("");
  // registered character without a photo: send it right here, then the list re-checks itself
  $$("[data-fotofalta]").forEach((inp) => (inp.onchange = async () => {
    if (!inp.files[0]) return;
    const fd = new FormData();
    fd.append("imagem", inp.files[0]);
    inp.parentElement.firstChild.textContent = "Salvando a foto… (se tiver fundo, a remoção leva ~30 s) ";
    inp.parentElement.classList.add("ocupado");
    try {
      await api(`/api/personagens/${inp.dataset.fotofalta}/imagem`, { method: "POST", body: fd });
      await loadLib();
      BATCH = await api(`/api/lotes/${b.id}/reanalisar`, { method: "POST" });
      renderBatch(BATCH);
    } catch (err) {
      alert(err.message);
      inp.parentElement.classList.remove("ocupado");
    }
  }));
  $$("[data-cadastrar]").forEach((btn) => (btn.onclick = () => {
    fecharLote();
    showTab("personagens");
    form.nome.value = btn.dataset.cadastrar.replace(/\w\S*/g, (w) => w[0] + w.slice(1).toLowerCase());
    form.nome.focus();
  }));
  // options
  const musicSel = $("#opt-musica");
  musicSel.innerHTML = `<option value="nenhuma">Sem música</option>
    <option value="personagem" ${LIB.musicas.length ? "" : "disabled"}>Música do personagem (rodízio, combina com ele)</option>
    <option value="aleatoria" ${LIB.musicas.length ? "" : "disabled"}>Aleatória da biblioteca (uma por vídeo)</option>
    ${LIB.musicas.map((m) => `<option value="${m.id}">${esc(m.nome)}</option>`).join("")}`;
  const chars = [...new Set(b.videos.filter((v) => v.template === "T02").flatMap((v) => v.personagens))]
    .map((p) => [p, LIB.personagens.find((c) => c.id === b.videos.find((v) => v.personagens_status?.[p])?.personagens_status[p])])
    .filter(([, c]) => c);
  $("#card-fundos").classList.toggle("hide", !chars.length);
  $("#opt-fundos").innerHTML = chars.map(([p, c]) => `<div class="fundo-row"><span>${esc(c.nome)}</span>
    <select data-personagem="${esc(p)}"><option value="auto" selected>Rodízio automático (${(c.fundos?.length ? c.fundos : [c.fundo]).length} fundos)</option>${LIB.fundos.map((f) => `<option value="${f.id}">${esc(f.nome)}</option>`).join("")}</select></div>`).join("");
  syncStart();
  $$(".chk").forEach((c) => (c.onchange = syncStart));
}
$("#chk-all").onchange = (e) => { $$(".chk:not(:disabled)").forEach((c) => (c.checked = e.target.checked)); syncStart(); };
$("#opt-musica").onchange = () => $("#vol-wrap").classList.toggle("hide", $("#opt-musica").value === "nenhuma");
$("#opt-volume").oninput = (e) => ($("#vol-val").textContent = `${e.target.value}%`);
$("#vol-wrap").classList.add("hide");

function abrirLote() {  // board: popup; traditional mode: the list right under the upload area, as before
  if (!BATCH) return;
  if (MODO === "placa") return $("#lote").classList.remove("hide");
  $("#trad-lote").classList.remove("hide");
  $("#trad-lote").scrollIntoView({ behavior: "smooth", block: "start" });
}
function fecharLote() { $("#lote").classList.add("hide"); if (!BATCH) $("#trad-lote").classList.add("hide"); }
async function limparLote() {
  if (BATCH) api(`/api/lotes/${BATCH.id}`, { method: "DELETE" }).catch(() => {});
  BATCH = null;
  ITENS = [];
  fecharLote();
  $("#lote-mini").classList.add("hide");
  $("#start-info").textContent = "";
  syncStart();
  updateHome([]);
}
$("#btn-limpar").onclick = () => { if (confirm("Tirar todos os roteiros da lista?")) limparLote(); };
document.body.append($("#lote"));  // above the sticky header
$("#lote-abrir").onclick = abrirLote;
$("#lote-fechar").onclick = fecharLote;
$("#lote-fechar-x").onclick = fecharLote;
$("#lote").onclick = (e) => { if (e.target.id === "lote") fecharLote(); };
document.addEventListener("keydown", (e) => {  // Esc closes the top popup first
  if (e.key !== "Escape") return;
  if (!$("#modal-add").classList.contains("hide")) return fecharAdd();
  fecharLote();
});
$("#lote-iniciar").onclick = () => $("#btn-iniciar").click();

function syncStart() {
  const n = BATCH ? $$(".chk:checked").length : 0;
  if (BATCH) {  // summary on the panel + the popup's start button
    const total = BATCH.videos.length, ok = BATCH.videos.filter((v) => v.pronto_para_gerar).length, bad = total - ok;
    $("#lote-mini").classList.remove("hide");
    $("#lote-mini-txt").innerHTML = `📄 <b>${total} roteiro${total > 1 ? "s" : ""} lido${total > 1 ? "s" : ""}</b>` +
      ` · <span style="color:var(--ok)">${ok} pronto${ok === 1 ? "" : "s"}</span>` +
      (bad ? ` · <span style="color:#ff9a92">${bad} com pendência</span>` : "") + ` · ${n} marcado${n === 1 ? "" : "s"}`;
    const trad = MODO === "trad";
    $("#lote-iniciar").disabled = !n;
    $("#lote-iniciar").textContent = trad ? (n ? `Gerar ${n} vídeo${n > 1 ? "s" : ""}` : "Gerar vídeos")
      : (n ? `Iniciar criação (${n})` : "Iniciar criação");
    $("#lote-info").textContent = !n ? "Selecione ao menos um roteiro pronto."
      : trad ? `Os vídeos são gerados um por vez, para o canal "${canalNome(CANAL)}". Acompanhe na aba Vídeos criados.`
      : `Vai para o canal "${canalNome(CANAL)}". Formato, legenda e música vêm do painel.`;
  }
  $("#reator-label").textContent = n ? `Iniciar criação (${n})` : "Iniciar criação";
  if (!BATCH) return;
  $("#start-info").textContent = n ? `${n} vídeo${n > 1 ? "s" : ""} para o canal "${canalNome(CANAL)}". ` +
    "Os vídeos são gerados um por vez." : "Marque ao menos um roteiro pronto na lista abaixo.";
  if (!ATIVOS) $("#etapa").textContent = n ? "Pronto para criar. Clique no botão." : "Nenhum roteiro marcado.";
}
$("#btn-reanalisar").onclick = async () => { BATCH = await api(`/api/lotes/${BATCH.id}/reanalisar`, { method: "POST" }); renderBatch(BATCH); };
$("#btn-iniciar").onclick = async () => {
  if (!BATCH) {
    $("#drop-status").innerHTML = '<span style="color:var(--warn)">Envie um roteiro primeiro (passo 2).</span>';
    $("#drop").scrollIntoView({ behavior: "smooth", block: "center" });
    return;
  }
  const ids = $$(".chk:checked").map((c) => c.value);
  if (!ids.length) return abrirLote();
  const fundos = Object.fromEntries($$("#opt-fundos select").map((s) => [s.dataset.personagem, s.value]));
  const opcoes = { musica: $("#opt-musica").value, volume: $("#opt-volume").value / 100, fundos, canal: CANAL,
    modelo_entrevista: MODELO_ENT };
  if (MODO === "placa") opcoes.estilo = estilo();  // traditional mode = the approved look (vertical, Poppins, gold)
  try {
    await api(`/api/lotes/${BATCH.id}/iniciar`, json("POST", { videos: ids, opcoes }));
  } catch (err) {
    const msg = `<span style="color:var(--bad)">${esc(err.message)}</span>`;
    $("#lote-info").innerHTML = msg;
    return ($("#start-info").innerHTML = msg);
  }
  BATCH = null;
  ITENS = [];
  fecharLote();
  $("#lote-mini").classList.add("hide");
  if (MODO === "trad") return showTab("fila");  // as before: go to the queue
  $("#start-info").innerHTML = `${ids.length} vídeo${ids.length > 1 ? "s" : ""} na fila. ` +
    '<a href="#" data-ir="fila">Acompanhar em Vídeos criados →</a>';
  $("#etapa").textContent = "Na fila…";
  syncStart();
  loadQueue();
};
$("#start-info").onclick = (e) => { if (e.target.dataset.ir) { e.preventDefault(); showTab(e.target.dataset.ir); } };

// ------------------------------------------------------------------ home panel: templates, format, captions
let TEMPLATE = "T02";  // the one template chosen on the board
let MODO = "placa";    // "placa" (circuit board) or "trad" (the page as it was before)
let ESTILOS = null;  // fonts, formats and defaults from /api/estilos
let ATIVOS = 0;      // videos queued or rendering (lights the board)
const store = {
  get(k, d) { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* private mode */ } },
};
const estilo = () => ({ formato: $(".fmt-card[aria-pressed=true]")?.dataset.fmt || "vertical", fonte: $("#opt-fonte").value,
  tamanho: +$("#opt-tamanho").value, cor: $("#opt-cor").value, cor_texto: $("#opt-cor-texto").value });

function drawBoard() {  // VC motherboard outline, drawn at the panel's real size
  const box = $("#placa"), w = box.offsetWidth, h = box.offsetHeight, o = 14, k = w / 600;
  if (!w || !h) return;
  const pts = [[40, 0], [15, 0], [0, 15], [0, h - 125], [10 * k, h - 105], [220 * k, h - 35], [250 * k, h - 15],
    [280 * k, h], [w - 280 * k, h], [w - 250 * k, h - 15], [w - 220 * k, h - 35], [w - 10 * k, h - 105], [w, h - 125],
    [w, 15], [w - 15, 0], [w - 40, 0]];
  $("#placa-path").setAttribute("d", "M" + pts.map(([x, y]) => `${(x + o).toFixed(1)} ${(y + o).toFixed(1)}`).join(" L") + " Z");
  let deco = "";
  for (let y = 70, i = 0; y < h - 190; y += 96, i++) {  // traces in the side margins only, so they never run under text
    const d = 16 + (i % 3) * 7;
    for (const side of [0, 1]) {
      const X = (x) => (side ? w - x : x) + o;
      deco += `<path class="trace" d="M${X(0)} ${y + o} L${X(10)} ${y + o} L${X(10 + d)} ${y + o + d} L${X(10 + d)} ${y + o + d + 22}"/>` +
        `<circle class="node" cx="${X(10 + d)}" cy="${y + o + d + 22}" r="3"/><circle class="node" cx="${X(10)}" cy="${y + o}" r="2.5"/>`;
    }
  }
  for (const f of [0.28, 0.52]) {  // side connectors
    deco += `<rect class="pin" x="${o - 10}" y="${o + h * f}" width="10" height="40" rx="2"/>` +
      `<rect class="pin" x="${o + w}" y="${o + h * f}" width="10" height="40" rx="2"/>`;
  }
  deco += `<rect class="pin" x="${o}" y="${o}" width="10" height="10" opacity=".3"/><rect class="pin" x="${o + w - 10}" y="${o}" width="10" height="10" opacity=".3"/>`;
  $("#placa-deco").innerHTML = deco;
}
new ResizeObserver(drawBoard).observe($("#placa"));

function renderPreview() {
  const e = estilo(), horiz = e.formato === "horizontal";
  const frame = $("#leg-prev");
  frame.classList.toggle("h", horiz);
  const scale = frame.offsetWidth / (horiz ? 1920 : 1080);
  const span = $("#leg-prev-txt");
  span.style.fontFamily = `"leg-${e.fonte}", sans-serif`;
  span.style.fontSize = `${(e.tamanho * scale).toFixed(1)}px`;
  span.style.webkitTextStroke = `${(2 * Math.max(3, Math.round(7 * e.tamanho / 84)) * scale).toFixed(2)}px #000`;
  span.style.color = e.cor_texto;
  span.innerHTML = `<span style="position:static;color:${e.cor}">ESSA É</span> A SUA LEGENDA`;
  $("#tam-val").textContent = `${e.tamanho} px`;
  $("#fmt-aviso").classList.toggle("hide", !horiz);
}

function saveStyle() { store.set("estilo", estilo()); renderPreview(); }

async function loadEstilos() {
  ESTILOS = await api("/api/estilos");
  const saved = { ...ESTILOS.padrao, ...store.get("estilo", {}) };
  for (const f of ESTILOS.fontes) {  // the real font files, so the preview matches the video
    new FontFace(`leg-${f.id}`, `url(${f.url})`, { display: "swap" }).load().then((ff) => { document.fonts.add(ff); renderPreview(); }).catch(() => {});
  }
  $("#opt-fonte").innerHTML = ESTILOS.fontes.map((f) => `<option value="${f.id}">${esc(f.nome)}</option>`).join("");
  $("#opt-fonte").value = ESTILOS.fontes.some((f) => f.id === saved.fonte) ? saved.fonte : ESTILOS.padrao.fonte;
  $("#opt-tamanho").min = ESTILOS.tamanho_min;
  $("#opt-tamanho").max = ESTILOS.tamanho_max;
  $("#opt-tamanho").value = saved.tamanho;
  $("#opt-cor").value = saved.cor.toLowerCase();
  $("#opt-cor-texto").value = saved.cor_texto.toLowerCase();
  const ordem = ["vertical", "horizontal"];  // the JSON comes back sorted alphabetically
  $("#fmt-grid").innerHTML = Object.entries(ESTILOS.formatos).sort(([a], [b]) => ordem.indexOf(a) - ordem.indexOf(b)).map(([id, f]) => `<button type="button" class="fmt-card" data-fmt="${id}"
    aria-pressed="${id === saved.formato}"><span class="fmt-shape ${id === "horizontal" ? "h" : "v"}"></span>
    <span class="tpl-txt"><b>${esc(f.nome)}</b><span class="small muted">${esc(f.uso)} · ${f.largura}×${f.altura}</span></span>
    <span class="tpl-check">✓</span></button>`).join("");
  if (!$(".fmt-card[aria-pressed=true]")) $(".fmt-card").setAttribute("aria-pressed", "true");
  $$(".fmt-card").forEach((b) => (b.onclick = () => {
    $$(".fmt-card").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
    saveStyle();
  }));
  ["#opt-fonte", "#opt-tamanho", "#opt-cor", "#opt-cor-texto"].forEach((s) => ($(s).oninput = saveStyle));
  renderPreview();
}
$("#leg-padrao").onclick = () => {
  const p = ESTILOS.padrao;
  $("#opt-fonte").value = p.fonte;
  $("#opt-tamanho").value = p.tamanho;
  $("#opt-cor").value = p.cor.toLowerCase();
  $("#opt-cor-texto").value = p.cor_texto.toLowerCase();
  saveStyle();
};

// cover title: font + one colour or a sequence (saved in the app, so every new cover follows it)
let CAPA = null;
const NOMES_COR = {};
const nomeCor = (h) => NOMES_COR[h.toUpperCase()] || h;
function renderCapa() {
  const c = CAPA, seq = c.modo === "sequencia", prox = seq ? c.proxima : 0;
  $("#capa-fonte").value = c.fonte;
  $("#capa-modo").value = c.modo;
  $("#capa-cores").innerHTML = c.cores.map((cor, i) => `<label class="capa-cor${i === prox ? " prox" : ""}">
    <input type="color" value="${cor.toLowerCase()}" data-i="${i}"><span>${i === prox ? "próxima" : seq ? i + 1 + "ª" : ""}</span>
    ${c.cores.length > 1 ? `<button type="button" class="x" data-x="${i}" title="Tirar esta cor">×</button>` : ""}</label>`).join("");
  const cor = c.cores[prox];
  $("#capa-prev-txt").style.color = cor;
  $("#capa-prev-txt").style.fontFamily = `"leg-${c.fonte}", sans-serif`;
  $("#capa-prev-nome").style.background = cor;
  const depois = c.cores.slice(prox + 1).concat(c.cores.slice(0, prox)).map(nomeCor).join(", ");
  $("#capa-prox").textContent = seq ? `Próxima capa: ${nomeCor(cor)}${depois ? " · depois " + depois : ""}` : `Todas as capas: ${nomeCor(cor)}`;
  $$("#capa-cores input[type=color]").forEach((inp) => (inp.onchange = () => { c.cores[+inp.dataset.i] = inp.value.toUpperCase(); salvarCapa(); }));
  $$("#capa-cores .x").forEach((b) => (b.onclick = (ev) => { ev.preventDefault(); c.cores.splice(+b.dataset.x, 1); c.proxima = 0; salvarCapa(); }));
}
async function salvarCapa() {
  try {
    CAPA = await api("/api/capa", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fonte: CAPA.fonte, modo: CAPA.modo, cores: CAPA.cores, proxima: CAPA.proxima }) });
  } catch (err) { alert(err.message); }
  renderCapa();
}
async function loadCapa() {
  try { CAPA = await api("/api/capa"); } catch {
    $("#passo-capa").classList.add("off");  // the running app is older than this page: restart it to use this
    $("#capa-aviso").classList.remove("hide");
    CAPA = { fonte: "poppins_extra", modo: "sequencia", cores: ["#FFD400", "#39FF14", "#FFFFFF", "#FF2A2A", "#00E5FF"], proxima: 2,
      sugeridas: [{ nome: "Verde", cor: "#39FF14" }, { nome: "Branco", cor: "#FFFFFF" }, { nome: "Vermelho", cor: "#FF2A2A" },
        { nome: "Azul neon", cor: "#00E5FF" }, { nome: "Amarelo", cor: "#FFD400" }] };
  }
  for (const x of CAPA.sugeridas) NOMES_COR[x.cor.toUpperCase()] = x.nome;
  $("#capa-fonte").innerHTML = (ESTILOS?.fontes || []).map((f) => `<option value="${f.id}">${esc(f.nome)}</option>`).join("");
  $("#capa-sug").innerHTML = CAPA.sugeridas.map((x) => `<button type="button" style="background:${x.cor}" title="${esc(x.nome)}" data-c="${x.cor}"></button>`).join("");
  $$("#capa-sug button").forEach((b) => (b.onclick = () => { if (CAPA.cores.length < 12) { CAPA.cores.push(b.dataset.c); salvarCapa(); } }));
  $("#capa-fonte").onchange = () => { CAPA.fonte = $("#capa-fonte").value; salvarCapa(); };
  $("#capa-modo").onchange = () => { CAPA.modo = $("#capa-modo").value; salvarCapa(); };
  renderCapa();
}

// voice check (T02): what the automatic fix could not solve, with a click to jump to it in the video
const mmss = (t) => `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, "0")}`;
function vozInfo(v) {
  if (!Array.isArray(v.voz_alertas)) return "";
  const fixed = v.voz_corrigidos ? ` · ${v.voz_corrigidos} trecho(s) corrigido(s) sozinho` : "";
  if (!v.voz_alertas.length) return `<div class="small voz-ok" title="O áudio foi comparado com o roteiro">🎙️ Voz conferida${fixed}</div>`;
  const rows = v.voz_alertas.map((a) => `<li><button type="button" class="link small voz-seek" data-t="${a.no_video_s ?? ""}">${a.no_video_s != null ? mmss(a.no_video_s) : "?"}</button>
    ${esc(a.cena.replace("CENA_", "cena "))}: ${esc(a.tipo)} <span class="muted">${esc(a.detalhe)}</span></li>`).join("");
  return `<details class="voz-alertas"><summary>⚠️ ${v.voz_alertas.length} trecho(s) da voz para ouvir${fixed}</summary><ul>${rows}</ul>
    <p class="small muted">Clique no tempo para ir até o trecho. Se estiver ruim, use 🔄 para gerar de novo (as vozes boas são reaproveitadas).</p></details>`;
}
document.addEventListener("click", (ev) => {
  const b = ev.target.closest(".voz-seek");
  if (!b || b.dataset.t === "") return;
  const video = b.closest(".vcard")?.querySelector("video");
  if (video) { video.currentTime = Math.max(0, +b.dataset.t - 1); video.play().catch(() => {}); }
});

// one template at a time; the upload area changes with it
const DROP = {
  trad: { titulo: "Envie o roteiro", texto: "<b>Arraste aqui os roteiros</b> (.txt, .md ou .pdf), ou uma pasta com roteiros e imagens",
    arquivos: true, pasta: true, colar: true },
  T02: { titulo: "Envie os roteiros da entrevista", texto: "<b>Arraste aqui os roteiros</b> (.txt, .md ou .pdf). " +
    "Pode escolher mais de uma vez: cada roteiro entra na lista e vira um vídeo.", arquivos: true, pasta: false, colar: true },
  F01: { titulo: "Envie a pasta do episódio", texto: "<b>Escolha a pasta</b> com o roteiro e as imagens numeradas " +
    "(cena1.png, cena2.png...). Cada pasta é um episódio: escolha outra pasta para somar mais episódios, ou uma pasta " +
    "com várias pastas dentro.", arquivos: false, pasta: true, colar: false },
};
function syncDrop() {
  const d = DROP[MODO === "trad" ? "trad" : TEMPLATE];
  $("#drop-txt").innerHTML = d.texto;
  $("#passo2-titulo").textContent = d.titulo;
  $("#lbl-files").classList.toggle("hide", !d.arquivos);
  $("#lbl-folder").classList.toggle("hide", !d.pasta);
  $("#lbl-folder").classList.toggle("ghost", d.arquivos);  // the only button is the main one
  $("#colar").classList.toggle("hide", !d.colar);
}
function escolherTemplate(t) {
  TEMPLATE = t;
  store.set("template", t);
  $$(".tpl-card").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.tpl === t)));
  syncDrop();
  syncModeloEnt();
  if (BATCH) renderBatch(BATCH);
}
$$(".tpl-card").forEach((b) => (b.onclick = () => escolherTemplate(b.dataset.tpl)));
// the interview has two models: 1 = still portrait + sound bars (T02), 2 = mouth moving with SadTalker (T03)
var MODELO_ENT = store.get("modelo_entrevista", "T03") === "T02" ? "T02" : "T03";
function syncModeloEnt() {
  const box = $("#modelo-entrevista");
  if (!box) return;
  box.classList.toggle("hide", MODO !== "trad" && TEMPLATE !== "T02");
  $$(".mod-card").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.mod === MODELO_ENT)));
}
$$(".mod-card").forEach((b) => (b.onclick = () => {
  MODELO_ENT = b.dataset.mod;
  store.set("modelo_entrevista", MODELO_ENT);
  syncModeloEnt();
}));

function setModo(m) {  // board on/off: the shared pieces (upload, list, music) move to the visible layout
  MODO = m;
  store.set("modo", m);
  const trad = m === "trad";
  $("#modo-trad").classList.toggle("hide", !trad);
  $("#modo-placa").classList.toggle("hide", trad);
  (trad ? $("#trad-envio") : $("#placa-envio")).append($("#envio"));
  (trad ? $("#trad-lote") : $("#lote")).append($("#lote-box"));
  (trad ? $("#trad-opcoes") : $("#avancadas")).append($("#opcoes-box"));
  if (trad) $("#trad-opcoes").before($("#modelo-entrevista")); else $(".tpl-links").before($("#modelo-entrevista"));
  syncModeloEnt();
  $("#lote-box").classList.toggle("inline", trad);
  $("#lote-titulo").textContent = trad ? "Identificado" : "Roteiros identificados";
  $("#lote").classList.add("hide");
  $("#trad-lote").classList.toggle("hide", !(trad && BATCH));
  syncDrop();
  if (BATCH) renderBatch(BATCH); else syncStart();
  if (!trad) requestAnimationFrame(drawBoard);
}
$("#btn-desligar").onclick = () => setModo("trad");
$("#btn-ligar").onclick = () => setModo("placa");
escolherTemplate(store.get("template", "T02") === "F01" ? "F01" : "T02");
setModo(store.get("modo", "placa") === "trad" ? "trad" : "placa");
$("#btn-avancadas").onclick = () => $("#avancadas").classList.toggle("hide");

// ------------------------------------------------------------------ process dock (floating, every tab, never blocks)
const TAREFAS = new Map();  // id -> {titulo, detalhe, pct, ir}
let DOCK_FIM = null;        // short "done" note after the last task ends
function tarefa(id, t) {
  if (t) TAREFAS.set(id, t); else TAREFAS.delete(id);
  renderDock();
}
function concluido(texto) {
  DOCK_FIM = { texto, ate: Date.now() + 5000 };
  renderDock();
  setTimeout(renderDock, 5100);
}
function renderDock() {
  const items = [...TAREFAS.values()], working = items.length > 0;
  $("#btn-iniciar").classList.toggle("trabalhando", working);  // the reactor spins while anything is being done
  $("#placa").classList.toggle("ativo", working);
  const dock = $("#dock");
  if (!working && DOCK_FIM && Date.now() < DOCK_FIM.ate) {
    dock.innerHTML = `<div class="dock-item fim"><span class="dock-ok">✓</span><div class="dock-txt"><b>${esc(DOCK_FIM.texto)}</b></div></div>`;
    return dock.classList.remove("hide");
  }
  dock.classList.toggle("hide", !working);
  dock.innerHTML = items.map((t) => `<div class="dock-item" ${t.ir ? `data-ir="${t.ir}" title="Abrir ${t.ir === "fila" ? "Vídeos criados" : ""}"` : ""}>
    <span class="dock-gear" aria-hidden="true"></span><div class="dock-txt">
    <div class="dock-top"><b>${esc(t.titulo)}</b>${t.tempo ? `<span class="dock-tempo">${esc(t.tempo)}</span>` : ""}</div>
    ${t.detalhe ? `<span class="dock-nome">${esc(t.detalhe)}</span>` : ""}
    ${t.sub ? `<span>${esc(t.sub)}</span>` : ""}
    <div class="dock-bar ${t.pct == null ? "indet" : ""}"><div style="width:${t.pct ?? 35}%"></div></div></div></div>`).join("");
}
$("#dock").onclick = (e) => { const it = e.target.closest("[data-ir]"); if (it) showTab(it.dataset.ir); };

function acompanhar(chave, ativos, existem) {
  // a "run" = every item that was active since the dock last went quiet, so it can say "2 of 5"
  let run = store.get(chave, []).filter((k) => existem.has(k));  // deleted videos never count
  if (!ativos.length) { store.set(chave, []); return { run, fim: true }; }
  if (!ativos.some((k) => run.includes(k))) run = [];
  run = [...new Set([...run, ...ativos])];
  store.set(chave, run);
  return { run, fim: false };
}

function updateDock(batches) {
  const vids = batches.flatMap((b) => b.videos.map((v) => ({ ...v, key: `${b.id}/${v.id}` })));
  const byKey = Object.fromEntries(vids.map((v) => [v.key, v]));
  // videos being made
  const ativos = vids.filter((v) => ["na_fila", "gerando"].includes(v.status));
  const existem = new Set(vids.map((v) => v.key));
  const r = acompanhar("run_videos", ativos.map((v) => v.key), existem);
  if (ativos.length) {
    const feitos = r.run.filter((k) => byKey[k] && !["na_fila", "gerando"].includes(byKey[k].status)).length;
    const cur = ativos.find((v) => v.status === "gerando") || ativos[0];
    const desde = cur.status === "gerando" && cur.inicio ? Date.now() / 1000 - cur.inicio : null;
    tarefa("videos", { titulo: `Criando vídeo ${Math.min(feitos + 1, r.run.length)} de ${r.run.length}`, ir: "fila",
      tempo: desde != null ? `⏱ ${fmt(desde)}` : "", detalhe: cur.titulo || cur.arquivo,
      sub: [cur.template_nome, `${cur.cenas.length} cenas`, cur.status === "gerando" ? cur.etapa || "preparando" : "na fila"]
        .filter(Boolean).join(" · "),
      pct: cur.passos_total ? Math.min(95, (100 * cur.passos_feitos) / cur.passos_total) : 0 });
  } else if (TAREFAS.has("videos")) {
    const n = r.run.length, erros = r.run.filter((k) => byKey[k]?.status === "erro").length;
    tarefa("videos", null);
    concluido(erros ? `${n - erros} de ${n} vídeo(s) criados · ${erros} com erro` : n > 1 ? `${n} vídeos criados` : "Vídeo criado");
  }
  // uploads to Google Drive
  const subindo = vids.filter((v) => v.drive_etapa);
  const d = acompanhar("run_drive", subindo.map((v) => v.key), existem);
  if (subindo.length) {
    const feitos = d.run.filter((k) => byKey[k] && !byKey[k].drive_etapa).length;
    tarefa("drive", { titulo: `Enviando para o Drive ${Math.min(feitos + 1, d.run.length)} de ${d.run.length}`, ir: "fila",
      detalhe: `${subindo[0].titulo || subindo[0].arquivo} · ${subindo[0].drive_etapa}` });
  } else if (TAREFAS.has("drive")) {
    const erros = d.run.filter((k) => byKey[k]?.drive_erro).length;
    tarefa("drive", null);
    concluido(erros ? `Drive: ${d.run.length - erros} enviado(s), ${erros} com falha` : `${d.run.length} vídeo(s) enviados para o Drive`);
  }
}

function updateHome(batches) {  // progress bar under the panel + the floating dock
  updateDock(batches);
  FILA_SIGS = new Map(batches.flatMap((b) => b.videos).filter((v) => ["na_fila", "gerando"].includes(v.status))
    .map((v) => [assinatura(v), v.titulo]));
  const videos = batches.flatMap((b) => b.videos);
  const active = videos.filter((v) => ["na_fila", "gerando"].includes(v.status));
  ATIVOS = active.length;
  const cur = active.find((v) => v.status === "gerando");
  const pct = cur?.passos_total ? Math.min(95, (100 * cur.passos_feitos) / cur.passos_total) : 0;
  $("#prog-fill").style.width = `${ATIVOS ? pct : 0}%`;
  if (cur) {
    const rest = ATIVOS - 1;
    $("#etapa").textContent = `Criando "${cur.titulo || cur.arquivo}": ${cur.etapa || "preparando"}` +
      (rest ? ` · mais ${rest} na fila` : "");
  } else if (ATIVOS) {
    $("#etapa").textContent = `${ATIVOS} vídeo${ATIVOS > 1 ? "s" : ""} na fila…`;
  } else if (!BATCH) {
    $("#etapa").textContent = "Aguardando roteiro…";
  } else {
    syncStart();
  }
}

// ------------------------------------------------------------------ queue (grid of videos per batch)
const STATUS = { analisado: "Não iniciado", na_fila: "Na fila", gerando: "Gerando", pronto: "Pronto", erro: "Erro" };
const fmt = (s) => (s >= 60 ? `${Math.floor(s / 60)} min ${Math.round(s % 60)} s` : `${Math.round(s)} s`);
let pollTimer = null;

function busy(text) {  // locks the screen during long tasks so nothing is clicked twice
  $("#loading-text").textContent = text || "";
  $("#loading").classList.toggle("hide", !text);
}

function cardSig(v) {  // a card is redrawn only when this changes, so typing and playback are never interrupted
  if (v.status !== "pronto") return JSON.stringify([v.status, v.etapa, v.passos_feitos, v.erro, Math.floor(Date.now() / 5000)]);
  return JSON.stringify([v.status, v.apagado, v.drive?.video_id, v.metadados?.atualizado, v.capa_no_video,
    v.drive_etapa, v.drive_erro]);
}

function cardHTML(b, v) {
  const key = `${b.id}/${v.id}`;
  if (v.status !== "pronto") {
    const pct = v.passos_total ? Math.min(95, (100 * v.passos_feitos) / v.passos_total) : 0;
    const time = v.inicio ? fmt((v.fim || Date.now() / 1000) - v.inicio) : "";
    return `<div class="vcard pending" data-key="${key}" data-bid="${b.id}" data-vid="${v.id}"><div class="vthumb wait"><span class="status s-${v.status}">${STATUS[v.status]}</span></div>
      <div class="vinfo"><div class="t">${esc(v.titulo || v.arquivo)}</div>
      <div class="sub">${esc(v.template_nome)} · ${v.cenas.length} cenas${v.etapa && v.status === "gerando" ? " · " + esc(v.etapa) : ""}${time ? " · " + time : ""}</div>
      ${v.erro ? `<div class="small" style="color:#ff9a92">${esc(v.erro)}</div>` : ""}
      ${v.status === "erro" ? '<div class="vacts"><button class="btn small" data-act="refazer">🔄 Gerar de novo</button></div><div class="small msg"></div>' : ""}
      <div class="bar"><div style="width:${pct}%"></div></div></div></div>`;
  }
  const m = v.metadados || {};
  const poster = v.capa ? `${media(v.capa)}&t=${Math.round(v.fim || 0)}` : "";
  const thumb = v.apagado
    ? `<div class="vthumb gone">${poster ? `<img src="${poster}" alt="" onerror="this.remove()">` : ""}<span>Vídeo apagado</span></div>`
    : `<div class="vthumb ${v.formato === "horizontal" ? "h" : ""}"><video controls preload="none" playsinline ${poster ? `poster="${poster}"` : ""} src="${media(v.saida)}"></video></div>`;
  return `<div class="vcard" data-key="${key}" data-bid="${b.id}" data-vid="${v.id}">${thumb}
    <div class="vinfo">
      <div class="vtags"><span class="chip ${v.template === "T02" ? "t02" : "t01"}">${esc(v.template_nome)}</span>
        ${v.idioma ? `<span class="chip">${v.idioma === "en" ? "Inglês" : "Português"}</span>` : ""}
        ${v.serie ? `<span class="chip" title="${esc(v.serie)}">📺 ${esc(v.episodio_txt || "")}</span>` : ""}
        ${v.drive?.video_id ? `<a class="chip ok" href="${esc(v.drive.link || "#")}" target="_blank" rel="noopener" title="ID no Drive: ${esc(v.drive.video_id)}">✅ Enviado</a>` : ""}
        ${v.drive_etapa ? `<span class="chip">☁️ ${esc(v.drive_etapa)}</span>` : ""}
        ${v.drive_erro ? `<span class="chip bad" title="${esc(v.drive_erro)}">⚠️ Falha no envio</span>` : ""}
        ${m.origem === "local" ? `<span class="chip bad" title="${esc(m.aviso || "")}">texto automático</span>` : ""}
        ${m.origem === "roteiro" ? '<span class="chip ok" title="Título, descrição ou hashtags vieram do bloco METADADOS do roteiro">do roteiro</span>' : ""}
        ${m.editado ? '<span class="chip">editado</span>' : ""}</div>
      <label>Título<input class="m-titulo" value="${esc(m.titulo || v.titulo || "")}" placeholder="Título do post"></label>
      <label>Descrição<textarea class="m-descricao" rows="4" placeholder="Contexto + pergunta provocativa">${esc(m.descricao || "")}</textarea></label>
      <label>Hashtags<textarea class="m-hashtags" rows="2" placeholder="#tema #nicho">${esc(m.hashtags || "")}</textarea></label>
      ${v.inicio && v.fim ? `<div class="small muted tempo-criacao" title="Do início da geração até o vídeo ficar pronto">⏱ Levou ${fmt(v.fim - v.inicio)} para criar · ${v.cenas.length} cenas</div>` : ""}
      ${vozInfo(v)}
      ${v.ritmo ? `<div class="small muted" title="Tabela em app/data/ritmos.json">⏱️ Ritmo: ${esc(v.ritmo.nome)} (${Number(v.ritmo.fator).toFixed(2)}×)</div>` : ""}
      ${v.musica_credito ? `<div class="small muted">Crédito da música: ${esc(v.musica_credito)}</div>` : ""}
      <div class="vacts">
        <button class="btn small" data-act="novo" title="Refazer a descrição e as hashtags com a IA (substitui o que está escrito)">🆕 Novo</button>
        <button class="btn ghost small" data-act="salvar">💾 Salvar</button>
        <button class="btn ghost small" data-act="pasta" title="Abrir pasta">📂</button>
        ${v.capa ? `<a class="btn ghost small" href="${media(v.capa)}" download="capa_${esc(v.id)}.png" title="Baixar capa">🖼️</a>` : ""}
        <button class="btn ghost small" data-act="refazer" title="Gerar este vídeo de novo">🔄</button>
        ${v.apagado ? "" : '<button class="btn danger small" data-act="apagar" title="Apagar só o vídeo (.mp4)">🗑️</button>'}
        ${v.drive_erro && !v.drive?.video_id && !v.drive_etapa && !v.apagado
          ? '<button class="btn small" data-act="reenviar" title="Tentar enviar só este vídeo para o Drive de novo">☁️ Tentar enviar de novo</button>' : ""}
      </div><div class="small msg" ${v.drive_erro ? 'style="color:#ff9a92"' : ""}>${esc(v.drive_erro || "")}</div>
    </div></div>`;
}

function batchHead(b, vids) {
  const ready = vids.filter((v) => v.status === "pronto");
  const sent = ready.filter((v) => v.drive?.video_id).length;
  const toSend = ready.filter((v) => !v.drive?.video_id && !v.apagado).length;
  const files = ready.filter((v) => !v.apagado).length;
  const sentChip = !sent ? "" : sent === ready.length
    ? '<span class="chip ok">✅ Lote enviado</span>' : `<span class="chip">☁️ ${sent} de ${ready.length} enviados</span>`;
  return `<h2><button class="tog" data-lote-act="toggle" title="Mostrar ou esconder os vídeos">▾</button>
    <span class="lote-nome" data-lote-act="toggle">Lote ${esc(b.criado_em)}</span>
    <span>· ${ready.length} de ${vids.length} prontos ${b.opcoes?.musica && b.opcoes.musica !== "nenhuma" ? "· com música" : ""}</span>
    ${sentChip}</h2>
    <div class="lote-acts">
      <button class="btn ghost small" data-lote-act="metadados" ${ready.length ? "" : "disabled"}>🤖 Gerar metadados</button>
      <button class="btn small" data-lote-act="enviar" ${files ? "" : "disabled"}>${toSend
        ? `☁️ Enviar para o Drive (${toSend})` : "☁️ Enviar de novo para o Drive"}</button>
      ${CANAIS.length > 1 ? `<select class="mover-canal" title="Passar este lote (e os vídeos dele) para outro canal">
        <option value="">🔀 Mudar de canal…</option>${CANAIS.filter((c) => c.id !== canalDe(b))
          .map((c) => `<option value="${esc(c.id)}">${esc(c.nome)}</option>`).join("")}</select>` : ""}
      <button class="btn danger small" data-lote-act="apagar" ${files ? "" : "disabled"} title="Apaga só os .mp4; capas, metadados e projetos ficam">🗑️ Apagar vídeos</button>
      <button class="btn danger small" data-lote-act="apagar-lote" ${vids.some((v) => ["na_fila", "gerando"].includes(v.status)) ? "disabled" : ""} title="Apaga a pasta inteira do lote">✖ Apagar lote completo</button>
    </div>`;
}

async function loadQueue() {
  const [batches, sys] = await Promise.all([api("/api/lotes"), api("/api/sistema")]);
  const all = batches.filter((b) => b.videos.some((v) => v.status !== "analisado"));
  const active = all.flatMap((b) => b.videos).filter((v) => ["na_fila", "gerando"].includes(v.status)).length;
  updateHome(all);
  const started = all.filter((b) => canalDe(b) === CANAL);  // only the selected channel's batches
  $("#fila-canal").textContent = `· ${canalNome(CANAL)}`;
  $("#fila-badge").textContent = active;
  $("#fila-badge").classList.toggle("hide", !active);
  const gpuBusy = sys.gpu_usada_mb && sys.gpu_usada_mb > 4500;
  $("#gpu-alerta").classList.toggle("hide", !(gpuBusy && active));
  $("#gpu-alerta").textContent = `A placa de vídeo está com ${(sys.gpu_usada_mb / 1024).toFixed(1)} GB em uso. ` +
    "Feche jogos ou outros programas pesados: as falas precisam de cerca de 4 GB livres.";
  const fila = $("#fila");
  $("#fila-vazia").classList.toggle("hide", !!started.length);
  $$(".lote-fila", fila).forEach((el) => { if (!started.some((b) => b.id === el.dataset.bid)) el.remove(); });
  started.forEach((b, i) => {
    let sec = $(`.lote-fila[data-bid="${b.id}"]`, fila);
    if (!sec) {
      sec = document.createElement("div");
      sec.className = "lote-fila";
      sec.dataset.bid = b.id;
      sec.innerHTML = '<div class="lote-head"></div><div class="vgrid"></div>';
      sec.classList.toggle("fechado", closedBatches().includes(b.id));
      fila.insertBefore(sec, $$(".lote-fila", fila)[i] || null);
    }
    const vids = b.videos.filter((v) => v.status !== "analisado");
    const head = batchHead(b, vids);
    if (sec.dataset.head !== head) { $(".lote-head", sec).innerHTML = head; sec.dataset.head = head; }
    const grid = $(".vgrid", sec);
    vids.forEach((v, j) => {
      const key = `${b.id}/${v.id}`, sig = cardSig(v);
      const old = $(`[data-key="${key}"]`, grid);
      if (old && old.dataset.sig === sig) return;
      const tpl = document.createElement("template");
      tpl.innerHTML = cardHTML(b, v).trim();
      const card = tpl.content.firstChild;
      card.dataset.sig = sig;
      if (old) old.replaceWith(card); else grid.insertBefore(card, grid.children[j] || null);
    });
  });
  clearTimeout(pollTimer);
  const uploading = all.some((b) => b.videos.some((v) => v.drive_etapa));
  if (active || uploading) pollTimer = setTimeout(loadQueue, 2000);
}

function closedBatches() {  // batches the user collapsed (remembered in this browser only)
  try { return JSON.parse(localStorage.getItem("lotesFechados") || "[]"); } catch { return []; }
}

function toggleBatch(sec) {
  const closed = sec.classList.toggle("fechado");
  const ids = closedBatches().filter((id) => id !== sec.dataset.bid);
  try { localStorage.setItem("lotesFechados", JSON.stringify(closed ? [...ids, sec.dataset.bid] : ids)); } catch { /* private mode */ }
}

function cardMsg(card, text, bad) {
  const el = $(".msg", card);
  el.textContent = text;
  el.style.color = bad ? "#ff9a92" : "";
}

$("#fila").addEventListener("click", async (e) => {
  const btn = e.target.closest("[data-act], [data-lote-act]");
  if (!btn) return;
  if (btn.dataset.loteAct === "toggle") return toggleBatch(btn.closest(".lote-fila"));
  try {
    if (btn.dataset.act) {
      const card = btn.closest(".vcard");
      const url = `/api/lotes/${card.dataset.bid}/videos/${card.dataset.vid}`;
      const act = btn.dataset.act;
      if (act === "novo") {
        if (($(".m-descricao", card).value.trim() || $(".m-hashtags", card).value.trim()) &&
          !confirm("Gerar novos metadados com a IA? A descrição e as hashtags que estão escritas serão substituídas.")) return;
        const id = `meta-${card.dataset.bid}-${card.dataset.vid}`;
        tarefa(id, { titulo: "Gerando metadados", detalhe: $(".m-titulo", card).value || "descrição e hashtags" });
        try { await api(`${url}/metadados`, { method: "POST" }); } finally { tarefa(id, null); }
        concluido("Metadados gerados");
      } else if (act === "salvar") {
        await api(`${url}/metadados`, json("PUT", { titulo: $(".m-titulo", card).value,
          descricao: $(".m-descricao", card).value, hashtags: $(".m-hashtags", card).value }));
      } else if (act === "pasta") {
        const v = (await api(`/api/lotes/${card.dataset.bid}`)).videos.find((x) => x.id === card.dataset.vid);
        await api("/api/abrir", json("POST", { caminho: v.saida && !v.apagado ? v.saida : v.capa || v.projeto }));
        return;
      } else if (act === "apagar") {
        if (!confirm("Apagar o arquivo do vídeo (.mp4)? A capa, os metadados e os arquivos do projeto ficam.")) return;
        $("video", card)?.removeAttribute("src");
        await api(`${url}/arquivo`, { method: "DELETE" });
      } else if (act === "reenviar") {
        await api(`${url}/drive`, { method: "POST" });
      } else if (act === "refazer") {
        if (!card.classList.contains("pending") && !confirm("Gerar este vídeo de novo? O vídeo atual é substituído; " +
          "a descrição e as hashtags ficam. Ele volta a aparecer como não enviado.")) return;
        $("video", card)?.removeAttribute("src");
        await api(`${url}/refazer`, { method: "POST" });
      }
    } else {
      const sec = btn.closest(".lote-fila"), bid = sec.dataset.bid;
      const act = btn.dataset.loteAct;
      if (act === "metadados") {  // fills what is missing; when nothing is missing, offers to redo all
        const prontos = (await api(`/api/lotes/${bid}`)).videos.filter((v) => v.status === "pronto");
        const vazio = (v) => !(v.metadados?.descricao || "").trim() || !(v.metadados?.hashtags || "").trim();
        let alvo = prontos.filter(vazio), refazer = false;
        if (!alvo.length) {
          if (!confirm(`Todos os ${prontos.length} vídeo(s) já têm descrição e hashtags.\n\nGerar de novo para todos? ` +
            "O que está escrito será substituído.")) return;
          alvo = prontos;
          refazer = true;
        }
        const id = `meta-lote-${bid}`;
        try {
          for (const [i, v] of alvo.entries()) {
            tarefa(id, { titulo: `Gerando metadados ${i + 1} de ${alvo.length}`, detalhe: v.titulo || v.arquivo,
              pct: (100 * i) / alvo.length, ir: "fila" });
            await api(`/api/lotes/${bid}/videos/${v.id}/metadados${refazer ? "" : "?faltando=1"}`, { method: "POST" });
            loadQueue();
          }
        } finally { tarefa(id, null); }
        concluido(`Metadados gerados para ${alvo.length} vídeo(s)`);
      } else if (act === "apagar") {
        const vids = (await api(`/api/lotes/${bid}`)).videos.filter((v) => v.status === "pronto" && !v.apagado);
        const unsent = vids.filter((v) => !v.drive?.video_id).length;
        if (!confirm(`Apagar ${vids.length} vídeo(s) (.mp4) deste lote?` +
          (unsent ? `\n\nATENÇÃO: ${unsent} ainda não foram enviados para o Drive.` : "") +
          "\n\nA capa, os metadados e os arquivos do projeto ficam.")) return;
        $$("video", sec).forEach((el) => el.removeAttribute("src"));
        const id = `apagar-${bid}`;
        try {
          for (const [i, v] of vids.entries()) {
            tarefa(id, { titulo: `Apagando vídeo ${i + 1} de ${vids.length}`, detalhe: v.titulo || v.arquivo, pct: (100 * i) / vids.length });
            await api(`/api/lotes/${bid}/videos/${v.id}/arquivo`, { method: "DELETE" });
          }
        } finally { tarefa(id, null); }
        concluido(`${vids.length} vídeo(s) apagados`);
      } else if (act === "apagar-lote") {
        const vids = (await api(`/api/lotes/${bid}`)).videos.filter((v) => v.status === "pronto" && !v.apagado);
        const unsent = vids.filter((v) => !v.drive?.video_id).length;
        if (!confirm("Apagar o lote INTEIRO? Somem os roteiros, os vídeos, as capas, os metadados e os arquivos " +
          "de todos os vídeos dele. Não dá para desfazer." +
          (unsent ? `\n\nATENÇÃO: ${unsent} vídeo(s) pronto(s) ainda não foram enviados para o Drive.` : ""))) return;
        $$("video", sec).forEach((el) => el.removeAttribute("src"));
        tarefa(`apagar-lote-${bid}`, { titulo: "Apagando o lote", detalhe: "roteiros, vídeos, capas e metadados" });
        try { await api(`/api/lotes/${bid}`, { method: "DELETE" }); } finally { tarefa(`apagar-lote-${bid}`, null); }
        concluido("Lote apagado");
      } else if (act === "enviar") {
        await enviarDrive(bid);
      }
    }
    await loadQueue();
  } catch (err) {
    const card = btn.closest(".vcard");
    if (card) cardMsg(card, err.message, true); else alert(err.message);
  } finally {
    busy("");
  }
});

$("#fila").addEventListener("change", async (e) => {
  const sel = e.target.closest(".mover-canal");
  if (!sel?.value) return;
  const bid = sel.closest(".lote-fila").dataset.bid, to = sel.value;
  const b = await api(`/api/lotes/${bid}`);
  const sent = b.videos.filter((v) => v.drive?.video_id).length;
  if (!confirm(`Passar este lote do canal "${canalNome(canalDe(b))}" para o canal "${canalNome(to)}"?

` +
    "Quando você clicar em Enviar para o Drive, os vídeos vão para a pasta e a planilha desse canal." +
    (sent ? `

ATENÇÃO: ${sent} vídeo(s) já foram enviados para o Drive do canal antigo. Eles continuam ` +
      "lá (apague manualmente se quiser) e aqui voltam a aparecer como não enviados." : ""))) { sel.value = ""; return; }
  try {
    await api(`/api/lotes/${bid}/canal`, json("POST", { canal: to }));
    escolherCanal(to);  // show the batch in its new channel
  } catch (err) {
    sel.value = "";
    alert(err.message);
  }
});

async function enviarDrive(bid) {
  const [g, b] = await Promise.all([api("/api/google"), api(`/api/lotes/${bid}`)]);
  const canal = CANAIS.find((c) => c.id === canalDe(b));
  if (!canal?.pasta_id || !g.conectado) {
    alert(`Configure antes o Google Drive do canal "${canalNome(canalDe(b))}": credencial e link da pasta.`);
    return abrirGoogle();
  }
  const ready = b.videos.filter((v) => v.status === "pronto" && !v.apagado);
  const again = !ready.some((v) => !v.drive?.video_id);
  if (again && !confirm(`Todos os vídeos deste lote já foram enviados.\n\nQuer enviar novamente os ${ready.length} ` +
    `vídeo(s) para a pasta do canal "${canal.nome}"?\n${canal.pasta_link || ""}\n\nUse isso se a pasta mudou: ` +
    "os arquivos enviados antes continuam na pasta antiga, e a planilha do canal ganha linhas novas.")) return;
  await api(`/api/lotes/${bid}/drive`, json("POST", { de_novo: again }));  // progress shows in the dock
}

// ------------------------------------------------------------------ channels + Google Drive settings
async function loadCanais() {
  CANAIS = await api("/api/canais");
  if (!CANAIS.some((c) => c.id === CANAL)) CANAL = CANAIS[0]?.id || "";
  $("#canal").innerHTML = CANAIS.map((c) => `<option value="${esc(c.id)}" ${c.id === CANAL ? "selected" : ""}>` +
    `${esc(c.nome)}</option>`).join("");
}
function escolherCanal(id) {
  CANAL = id;
  try { localStorage.setItem("canal", id); } catch { /* private mode */ }
  $("#canal").value = id;
  if (BATCH) renderBatch(BATCH);  // the "for channel X" line under the scripts
  loadQueue();
}
$("#canal").onchange = (e) => escolherCanal(e.target.value);

let EDITANDO = null;  // channel id shown in the modal; null = creating a new one
function googleInfo(g) {
  $("#g-status").textContent = !g.credencial ? "Conta Google: falta a credencial." :
    !g.conectado ? "Conta Google: credencial salva, falta conectar (Salvar e conectar)." : "✅ Conta Google conectada.";
}
function canalInfo(c) {
  EDITANDO = c?.id || null;
  $("#g-titulo").textContent = c ? `Canal "${c.nome}" e Google Drive` : "Novo canal";
  $("#g-nome").value = c?.nome || "";
  $("#g-pasta").value = c?.pasta_link || "";
  $("#g-excluir").classList.toggle("hide", !c);
  $("#g-planilha").innerHTML = c?.planilha_link
    ? `Planilha deste canal: <a href="${esc(c.planilha_link)}" target="_blank" rel="noopener">abrir "Video Creator - Metadados"</a>` : "";
}
async function abrirGoogle(novo) {
  googleInfo(await api("/api/google"));
  canalInfo(novo === true ? null : CANAIS.find((c) => c.id === CANAL));
  $("#g-cred").value = "";
  $("#modal-google").classList.remove("hide");
  if (novo === true) $("#g-nome").focus();
}
$("#btn-google").onclick = () => abrirGoogle();
$("#btn-canal-novo").onclick = () => abrirGoogle(true);
$("#g-fechar").onclick = () => $("#modal-google").classList.add("hide");
$("#g-sair").onclick = async () => {
  if (confirm("Desconectar a conta Google? Vale para todos os canais; para enviar de novo será preciso fazer o login.")) googleInfo(await api("/api/google/desconectar", { method: "POST" }));
};
$("#g-excluir").onclick = async () => {
  const c = CANAIS.find((x) => x.id === EDITANDO);
  if (!c || !confirm(`Excluir o canal "${c.nome}"? A pasta e a planilha no Drive não são apagadas.`)) return;
  try {
    await api(`/api/canais/${EDITANDO}`, { method: "DELETE" });
    await loadCanais();
    escolherCanal(CANAL);
    $("#modal-google").classList.add("hide");
  } catch (err) {
    alert(err.message);
  }
};
$("#g-salvar").onclick = async () => {
  try {
    const nome = $("#g-nome").value.trim(), pasta = $("#g-pasta").value.trim();
    if (!nome) return $("#g-nome").focus();
    const file = $("#g-cred").files[0];
    if (file) {
      const fd = new FormData();
      fd.append("arquivo", file);
      googleInfo(await api("/api/google/credencial", { method: "POST", body: fd }));
    }
    let c = EDITANDO ? CANAIS.find((x) => x.id === EDITANDO) : null;
    if (!c) c = await api("/api/canais", json("POST", { nome }));
    else if (c.nome !== nome) c = await api(`/api/canais/${c.id}`, json("PUT", { nome }));
    EDITANDO = c.id;
    await loadCanais();
    escolherCanal(c.id);
    if (!pasta) {
      canalInfo(c);
      return alert(`Canal "${nome}" salvo. Para enviar os vídeos dele, cole o link da pasta do Drive e salve de novo.`);
    }
    busy("Conectando ao Google… Se abrir o login no navegador, entre com a conta do Drive e autorize.");
    c = await api(`/api/canais/${c.id}/conectar`, json("POST", { pasta }));
    googleInfo(await api("/api/google"));
    await loadCanais();
    canalInfo(c);
    busy("");
    alert(`Pronto! O canal "${c.nome}" envia para essa pasta, e a planilha "Video Creator - Metadados" dele está lá.`);
  } catch (err) {
    busy("");
    alert(err.message);
  }
};

// ------------------------------------------------------------------ AI settings
async function abrirIA() {
  const cfg = await api("/api/ia");
  const models = [...new Set([cfg.modelo, ...cfg.modelos])];
  $("#ia-modelo").innerHTML = models.map((m) => `<option ${m === cfg.modelo ? "selected" : ""}>${esc(m)}</option>`).join("");
  $("#ia-status").textContent = cfg.modelos.length ? `Ollama aberto · ${cfg.modelos.length} modelos instalados` :
    "O Ollama não está aberto. Abra o Ollama; sem ele o app usa um texto automático.";
  $("#ia-prompt").value = cfg.prompt;
  $("#ia-prompt").dataset.padrao = cfg.padrao;
  $("#modal-ia").classList.remove("hide");
}
$("#btn-ia").onclick = abrirIA;
$("#ia-padrao").onclick = () => ($("#ia-prompt").value = $("#ia-prompt").dataset.padrao);
$("#ia-fechar").onclick = () => $("#modal-ia").classList.add("hide");
$("#ia-salvar").onclick = async () => {
  await api("/api/ia", json("POST", { modelo: $("#ia-modelo").value, prompt: $("#ia-prompt").value }));
  $("#modal-ia").classList.add("hide");
};
$("#modal-close").onclick = () => { $("#modal-video").pause(); $("#modal").classList.add("hide"); };

loadLib();
loadEstilos().catch((err) => console.error("estilos:", err)).then(loadCapa);
loadCanais().then(() => escolherCanal(CANAL));
syncStart();
