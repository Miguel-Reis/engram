// Engram v11.1 — Dedicated 08 // Neural Cortex Studio Module (Zero-Build)
// =========================================================================
// 08 // LOCAL NEURAL CORTEX STUDIO (#neuralWorkspace) — ENGRAM v11.0
// =========================================================================
let neuralPageStatusCache = null;
let neuralPageV10Cache = null;
let neuralMlpAnimRunning = false;
let neuralMlpTick = 0;

function _populateNeuralPageWsSelect() {
  const sel = document.getElementById('neuralPageWsSelect');
  if (!sel) return;
  const cur = sel.value || 'all';
  const wsCounts = (graphData && graphData.filters && graphData.filters.workspace_counts) || {};
  const keys = Object.keys(wsCounts).sort((a, b) => (wsCounts[b] || 0) - (wsCounts[a] || 0));
  let html = '<option value="all">🌐 Todos Workspaces</option>';
  keys.forEach(ws => {
    html += `<option value="${escapeHtml(ws)}" ${ws === cur ? 'selected' : ''}>${escapeHtml(ws)} (${wsCounts[ws]})</option>`;
  });
  sel.innerHTML = html;
  if (cur && keys.includes(cur)) sel.value = cur;
}

async function fetchNeuralStudioPage() {
  _populateNeuralPageWsSelect();
  try {
    const [r11, r10] = await Promise.all([
      fetch('/api/v11/neural/status?workspace=all').then(r => r.json()).catch(() => null),
      fetch('/api/v10/status?workspace=all').then(r => r.json()).catch(() => null),
    ]);
    if (r11 && r11.ok) neuralPageStatusCache = r11;
    if (r10 && r10.ok) neuralPageV10Cache = r10;
    renderNeuralStudioPage();
  } catch (_e) {}
}

function renderNeuralStudioPage() {
  const s11 = neuralPageStatusCache || {};
  const s10 = neuralPageV10Cache || {};
  const l1 = s11.bi_encoder || s11.layer1_bi_encoder || {};
  const vec = s11.sqlite_vec || {};
  const l2 = s11.cross_encoder || s11.layer2_cross_encoder || {};
  const l3 = s11.personal_mlp || s11.layer3_personal_mlp || {};
  const l4 = s11.intent_head || s11.layer4_heads || {};
  const bt = s10.bitemporal || {};
  const hr = s10.hipporag || {};

  const pill = document.getElementById('neuralPageStatusPill');
  if (pill) {
    const l1Tag = (l1.onnx_ready || l1.cached_on_disk) ? 'ONNX 384-D' : `DENSE ${l1.dims || 256}-D`;
    const mlpTag = l3.trained ? `MLP ${l3.epochs || 0} EP · ${((Number(l3.accuracy || 0) <= 1 ? Number(l3.accuracy || 0) * 100 : Number(l3.accuracy || 0))).toFixed(0)}%` : 'MLP STANDBY';
    pill.textContent = `● ${l1Tag} · ${vec.loaded ? 'SQLITE-VEC C SIMD' : 'NUMPY'} · ${mlpTag}`;
  }

  const l1Badge = document.getElementById('npL1Badge');
  const l1Val = document.getElementById('npL1Value');
  const l1Sub = document.getElementById('npL1Sub');
  if (l1Badge) l1Badge.textContent = vec.loaded ? 'SQLITE-VEC SIMD' : 'NUMPY SIMD';
  if (l1Val) l1Val.textContent = `${l1.indexed_vectors ?? 0} / ${l1.total_active ?? 0} (${Number(l1.coverage_pct ?? 0).toFixed(1)}%)`;
  if (l1Sub) {
    const shortModel = (l1.model_name || '').split('/').pop().replace('paraphrase-multilingual-', '');
    l1Sub.textContent = `${l1.onnx_ready ? 'ONNX LIVE' : (l1.cached_on_disk ? 'ONNX CACHED' : 'DENSE 256-D')} · ${l1.vec_dims || l1.dims || 384}-D · ${shortModel}`;
    l1Sub.title = l1.model_name || '';
  }

  const l2Badge = document.getElementById('npL2Badge');
  const l2Val = document.getElementById('npL2Value');
  const l2Sub = document.getElementById('npL2Sub');
  if (l2Badge) l2Badge.textContent = l2.onnx_ready ? 'ONNX LIVE' : (l2.cached_on_disk ? 'CACHED' : 'FALLBACK');
  if (l2Val) l2Val.textContent = l2.onnx_ready ? 'Cross-Encoder ONNX' : (l2.cached_on_disk ? 'ONNX Pronto' : 'Bilinear Calibrado');
  if (l2Sub) {
    l2Sub.textContent = l2.model_name || 'Xenova/ms-marco-MiniLM-L-6-v2';
    l2Sub.title = l2Sub.textContent;
  }

  const l3Badge = document.getElementById('npL3Badge');
  const l3Val = document.getElementById('npL3Value');
  const l3Sub = document.getElementById('npL3Sub');
  const accPct = l3.accuracy != null ? ((Number(l3.accuracy) <= 1 ? Number(l3.accuracy) * 100 : Number(l3.accuracy)).toFixed(1) + '%') : '--';
  const lossStr = l3.final_loss != null ? Number(l3.final_loss).toFixed(4) : '--';
  if (l3Badge) l3Badge.textContent = `${l3.params_count || 625} PARAMS · ${l3.epochs || 0} EP`;
  if (l3Val) l3Val.textContent = l3.trained ? `Acc ${accPct} · Loss ${lossStr}` : 'Por Treinar';
  if (l3Sub) {
    l3Sub.textContent = `${l3.samples_count || 0} samples · 👍/👎 ${l3.feedback_total || 0} · Hebbian ${l3.hebbian_edges_updated || 0}`;
    l3Sub.title = l3Sub.textContent;
  }

  const l4Badge = document.getElementById('npL4Badge');
  const l4Val = document.getElementById('npL4Value');
  const l4Sub = document.getElementById('npL4Sub');
  if (l4Badge) l4Badge.textContent = `${l4.num_intents || 6} INTENTS`;
  if (l4Val) l4Val.textContent = `${bt.active_facts ?? bt.active_memories ?? 0} Ativos · ${hr.active_edges ?? 0} Arestas`;
  if (l4Sub) {
    l4Sub.textContent = `Bi-Temporal: ${bt.superseded_facts ?? bt.superseded_memories ?? 0} superseded · ${bt.supersedes_edges ?? 0} SUPERSEDES`;
    l4Sub.title = l4Sub.textContent;
  }

  const hebEl = document.getElementById('neuralMlpHebbianPill');
  if (hebEl) hebEl.textContent = `Hebbian: ${l3.hebbian_edges_updated || 0} sinapses`;

  // Render Loss Curve SVG
  const lossBox = document.getElementById('neuralPageLossBox');
  const lossSum = document.getElementById('neuralPageLossSummary');
  const lossHist = Array.isArray(l3.loss_history) ? l3.loss_history.map(Number).filter(Number.isFinite) : [];
  if (lossSum) {
    lossSum.textContent = lossHist.length ? `${lossHist[0].toFixed(4)} → ${lossHist[lossHist.length - 1].toFixed(4)} (${lossHist.length} ep)` : 'Sem histórico';
  }
  if (lossBox) {
    if (lossHist.length >= 2) {
      const sw = 340, sh = 160, pad = 16;
      const maxL = Math.max(...lossHist, 0.01);
      const minL = Math.min(...lossHist, 0);
      const span = Math.max(0.0001, maxL - minL);
      const pts = lossHist.map((v, idx) => {
        const x = pad + (idx / (lossHist.length - 1)) * (sw - pad * 2);
        const y = pad + (1 - (v - minL) / span) * (sh - pad * 2);
        return [x, y];
      });
      const linePath = pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ');
      const areaPath = `${linePath} L${pts[pts.length - 1][0].toFixed(1)},${sh - pad} L${pts[0][0].toFixed(1)},${sh - pad} Z`;
      lossBox.innerHTML = `
        <svg viewBox="0 0 ${sw} ${sh}" preserveAspectRatio="none" style="width:100%; height:168px; display:block;">
          <defs>
            <linearGradient id="npLossGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="#10b981" stop-opacity="0.45" />
              <stop offset="100%" stop-color="#10b981" stop-opacity="0.02" />
            </linearGradient>
          </defs>
          <line x1="${pad}" y1="${sh * 0.5}" x2="${sw - pad}" y2="${sh * 0.5}" stroke="rgba(255,255,255,0.08)" stroke-dasharray="3,4" />
          <path d="${areaPath}" fill="url(#npLossGrad)" />
          <path d="${linePath}" fill="none" stroke="#34d399" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" />
          <circle cx="${pts[0][0].toFixed(1)}" cy="${pts[0][1].toFixed(1)}" r="3.2" fill="#f59e0b" />
          <circle cx="${pts[pts.length - 1][0].toFixed(1)}" cy="${pts[pts.length - 1][1].toFixed(1)}" r="3.6" fill="#f8fafc" stroke="#10b981" stroke-width="1.6" />
          <text x="${pad}" y="12" fill="#94a3b8" font-size="9" font-family="monospace">Start: ${lossHist[0].toFixed(4)}</text>
          <text x="${sw - pad - 88}" y="${sh - 4}" fill="#6ee7b7" font-size="9" font-family="monospace">Final: ${lossHist[lossHist.length - 1].toFixed(4)}</text>
        </svg>
      `;
    } else {
      lossBox.innerHTML = '<div style="font-family:var(--font-mono); font-size:10px; color:var(--text-muted); text-align:center;">Clique em "🧠 Treinar MLP Pessoal" para gerar a curva de convergência.</div>';
    }
  }

  // Render all 12 learned feature weights
  const wBox = document.getElementById('neuralPageWeightsBox');
  const fi = l3.feature_importances || {};
  const entries = Object.entries(fi).sort((a, b) => Number(b[1]) - Number(a[1]));
  if (wBox) {
    if (!entries.length) {
      wBox.innerHTML = '<div style="color:var(--text-muted);">Treine o MLP para extrair as 12 importâncias de gradiente.</div>';
    } else {
      const maxW = Math.max(1, ...entries.map(e => Number(e[1] || 0)));
      wBox.innerHTML = entries.map(([fname, val], idx) => {
        const pct = Math.max(4, Math.round((Number(val) / maxW) * 100));
        const col = idx < 3 ? '#ff6a00' : (idx < 6 ? '#10b981' : '#38bdf8');
        return `
          <div style="display:grid; grid-template-columns:108px 1fr 38px; align-items:center; gap:6px;">
            <span style="color:#d4d4d8; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${escapeHtml(fname)}</span>
            <div style="height:6px; background:rgba(255,255,255,0.06); border-radius:3px; overflow:hidden;">
              <div style="width:${pct}%; height:100%; background:${col}; border-radius:3px;"></div>
            </div>
            <span style="text-align:right; color:#fbbf24;">${Number(val).toFixed(1)}%</span>
          </div>
        `;
      }).join('');
    }
  }
}

function startNeuralMlpCanvasLoop() {
  if (neuralMlpAnimRunning) return;
  neuralMlpAnimRunning = true;
  requestAnimationFrame(renderNeuralMlpCanvas);
}

function renderNeuralMlpCanvas() {
  if (activeMainView !== 'neural') {
    neuralMlpAnimRunning = false;
    return;
  }
  const c = document.getElementById('neuralMlpCanvas');
  if (!c) {
    neuralMlpAnimRunning = false;
    return;
  }
  const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
  const cssW = Math.max(240, Math.round(c.clientWidth || 540));
  const cssH = Math.max(150, Math.round(c.clientHeight || 186));
  if (Math.abs(c.width - Math.round(cssW * dpr)) > 2 || Math.abs(c.height - Math.round(cssH * dpr)) > 2) {
    c.width = Math.round(cssW * dpr);
    c.height = Math.round(cssH * dpr);
  }
  const g = c.getContext('2d');
  if (!g) {
    neuralMlpAnimRunning = false;
    return;
  }
  g.setTransform(dpr, 0, 0, dpr, 0, 0);
  g.clearRect(0, 0, cssW, cssH);

  neuralMlpTick += 0.032;
  const fi = (neuralPageStatusCache && neuralPageStatusCache.personal_mlp && neuralPageStatusCache.personal_mlp.feature_importances) || {};
  const inLabels = ['cosine', 'bm25', 'ppr', 'imp', 'access', 'recency', 'pinned', 'ws', 'canon', 'degree', 'active', 'cross'];
  const fiKeys = ['neural_cosine', 'bm25_norm', 'ppr_score', 'importance_norm', 'access_log', 'recency_decay', 'is_pinned', 'ws_exact', 'is_canonical_cat', 'graph_degree_norm', 'is_active', 'cross_score'];
  const layers = [
    { count: 12, x: cssW * 0.14, col: '#ff8c1a', title: 'INPUT (12)' },
    { count: 12, x: cssW * 0.42, col: '#fbbf24', title: 'HIDDEN 1 (24 ReLU)' },
    { count: 8,  x: cssW * 0.69, col: '#10b981', title: 'HIDDEN 2 (12 ReLU)' },
    { count: 1,  x: cssW * 0.90, col: '#38bdf8', title: 'P(USEFUL)' }
  ];

  const nodesByLayer = layers.map((ly, li) => {
    const arr = [];
    const topY = 24;
    const botY = cssH - 18;
    for (let i = 0; i < ly.count; i++) {
      const y = ly.count === 1 ? (topY + botY) * 0.5 : topY + (i / (ly.count - 1)) * (botY - topY);
      const wImp = li === 0 ? Math.min(1, Math.max(0.18, Number(fi[fiKeys[i]] || 8) / 18)) : 0.65;
      arr.push({ x: ly.x, y, wImp, label: li === 0 ? inLabels[i] : '' });
    }
    return arr;
  });

  // Draw weighted synaptic connections + travelling forward-pass pulses
  for (let li = 0; li < nodesByLayer.length - 1; li++) {
    const src = nodesByLayer[li];
    const dst = nodesByLayer[li + 1];
    for (let i = 0; i < src.length; i++) {
      for (let j = 0; j < dst.length; j++) {
        if (li < 2 && ((i + j * 3) % 3 !== 0)) continue;
        const a = src[i], b = dst[j];
        const strength = (a.wImp + b.wImp) * 0.5;
        g.strokeStyle = li === 0 ? `rgba(255, 120, 26, ${(0.08 + strength * 0.22).toFixed(2)})` : (li === 1 ? 'rgba(251, 191, 36, 0.16)' : 'rgba(16, 185, 129, 0.34)');
        g.lineWidth = li === 2 ? 1.15 : 0.7;
        g.beginPath();
        g.moveTo(a.x, a.y);
        g.lineTo(b.x, b.y);
        g.stroke();

        // Forward-prop electric spark
        if ((i + j) % 4 === 0) {
          const t = (neuralMlpTick * (0.65 + (i % 3) * 0.15) + li * 0.33 + i * 0.11 + j * 0.07) % 1;
          const px = a.x + (b.x - a.x) * t;
          const py = a.y + (b.y - a.y) * t;
          g.fillStyle = li === 2 ? '#6ee7b7' : '#ffffff';
          g.beginPath();
          g.arc(px, py, 1.4, 0, Math.PI * 2);
          g.fill();
        }
      }
    }
  }

  // Draw neurons + layer headers
  g.font = '700 8px "JetBrains Mono", monospace';
  layers.forEach((ly, li) => {
    g.fillStyle = ly.col;
    g.textAlign = 'center';
    g.fillText(ly.title, ly.x, 12);

    nodesByLayer[li].forEach(n => {
      const pulse = 1 + Math.sin(neuralMlpTick * 2.2 + n.y * 0.05) * 0.16;
      const r = (li === 3 ? 8.5 : (li === 0 ? 2.6 + n.wImp * 2.4 : 3.2)) * pulse;
      g.fillStyle = ly.col;
      g.globalAlpha = 0.24;
      g.beginPath();
      g.arc(n.x, n.y, r * 2.0, 0, Math.PI * 2);
      g.fill();

      g.globalAlpha = 1;
      g.beginPath();
      g.arc(n.x, n.y, r, 0, Math.PI * 2);
      g.fill();

      g.fillStyle = '#ffffff';
      g.beginPath();
      g.arc(n.x, n.y, Math.max(0.9, r * 0.38), 0, Math.PI * 2);
      g.fill();

      if (li === 0 && n.label) {
        g.textAlign = 'right';
        g.fillStyle = '#94a3b8';
        g.fillText(n.label, n.x - 8, n.y + 2.8);
      }
    });
  });
  g.textAlign = 'left';

  requestAnimationFrame(renderNeuralMlpCanvas);
}

async function runNeuralPageWarmupUI() {
  const btn = document.getElementById('btnNeuralPageWarmup');
  if (btn) { btn.disabled = true; btn.textContent = '⏳ A carregar ONNX + sqlite-vec...'; }
  try {
    const res = await fetch('/api/v11/neural/warmup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ load_reranker: true, index_limit: 2500 })
    });
    const data = await res.json();
    if (data && data.ok) {
      if (data.status) neuralPageStatusCache = data.status;
      renderNeuralStudioPage();
      showToast(`🔥 ONNX 384-D + sqlite-vec ativos (${data.warmup?.index_result?.total_indexed || 0} vetores)!`);
    } else {
      showToast('❌ Falha no warmup ONNX: ' + ((data && data.error) || 'erro'));
    }
  } catch (_e) {
    showToast('❌ Erro de rede no warmup ONNX');
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = '🔥 Warmup ONNX + sqlite-vec'; }
  }
}

async function runNeuralPageTrainUI() {
  const btn = document.getElementById('btnNeuralPageTrain');
  const epSel = document.getElementById('neuralPageEpochsSelect');
  const epochs = epSel ? parseInt(epSel.value, 10) || 50 : 50;
  if (btn) { btn.disabled = true; btn.textContent = '⏳ A treinar MLP...'; }
  try {
    const res = await fetch('/api/v11/neural/train', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ epochs, hebbian_sync: true })
    });
    const data = await res.json();
    if (data && data.ok) {
      if (data.status) neuralPageStatusCache = data.status;
      renderNeuralStudioPage();
      const tr = data.training || {};
      showToast(`🧠 MLP treinado (${epochs} ep em ${tr.elapsed_ms || 0}ms): Loss ${Number(tr.initial_loss || 0).toFixed(3)} → ${Number(tr.final_loss || 0).toFixed(4)} · ${tr.hebbian_edges_updated || 0} sinapses Hebbian!`);
    } else {
      showToast('❌ Erro no treino MLP: ' + ((data && data.error) || 'erro'));
    }
  } catch (_e) {
    showToast('❌ Erro de rede no treino MLP');
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = '🧠 Treinar MLP Pessoal'; }
  }
}

async function runNeuralPageSearchUI() {
  const qEl = document.getElementById('neuralPageQueryInput');
  const wsEl = document.getElementById('neuralPageWsSelect');
  const rrEl = document.getElementById('neuralPageChkRerank');
  const mlpEl = document.getElementById('neuralPageChkMlp');
  const intentBar = document.getElementById('neuralPageIntentBar');
  const outEl = document.getElementById('neuralPageSearchOutput');
  const q = (qEl ? qEl.value : '').trim();
  if (!q) {
    showToast('Escreva uma query para pesquisa neural de 4 camadas.');
    if (qEl) qEl.focus();
    return;
  }
  if (outEl) outEl.innerHTML = '<div style="color:#34d399;">🧠 A executar pesquisa 4 camadas (ONNX + sqlite-vec + Cross-Encoder + MLP)...</div>';
  try {
    const ws = wsEl ? wsEl.value : 'all';
    const rr = rrEl && rrEl.checked ? '1' : '0';
    const mlp = mlpEl && mlpEl.checked ? '1' : '0';
    const url = `/api/v11/neural/search?q=${encodeURIComponent(q)}&workspace=${encodeURIComponent(ws)}&top_k=8&rerank=${rr}&mlp=${mlp}`;
    const res = await fetch(url);
    const data = await res.json();
    if (!res.ok || !data || data.ok === false) {
      if (outEl) outEl.innerHTML = `<div style="color:#fda4af;">❌ ${escapeHtml((data && data.error) || 'Falha na pesquisa neural')}</div>`;
      return;
    }
    const intentObj = data.intent || {};
    const corObj = data.correction || {};
    if (intentBar) {
      const corPct = Math.round(Number(corObj.correction_prob || 0) * 100);
      intentBar.innerHTML = `
        <span class="tk-chip" style="background:rgba(16,185,129,0.14); border:1px solid rgba(16,185,129,0.4); color:#6ee7b7; padding:2px 7px; border-radius:5px;">🎯 Intent: ${escapeHtml(intentObj.intent || 'unknown')} (${Math.round(Number(intentObj.confidence || 0) * 100)}%)</span>
        <span class="tk-chip" style="background:rgba(255,106,0,0.12); border:1px solid rgba(255,106,0,0.35); color:#ffb020; padding:2px 7px; border-radius:5px;">⚡ ${Number(data.elapsed_ms || 0).toFixed(1)}ms · ${data.sqlite_vec_used ? 'sqlite-vec SIMD' : 'NumPy'}</span>
        <span class="tk-chip" style="background:${corObj.is_correction ? 'rgba(245,158,11,0.18)' : 'rgba(148,163,184,0.10)'}; border:1px solid ${corObj.is_correction ? 'rgba(245,158,11,0.45)' : 'rgba(148,163,184,0.22)'}; color:${corObj.is_correction ? '#fde68a' : '#94a3b8'}; padding:2px 7px; border-radius:5px;">🛡️ Correção: ${corPct}%</span>
      `;
    }
    const results = Array.isArray(data.results) ? data.results : [];
    if (!results.length) {
      if (outEl) outEl.innerHTML = '<div style="color:var(--text-muted);">Sem resultados encontrados para esta query.</div>';
      return;
    }
    if (outEl) {
      outEl.innerHTML = results.map((r, idx) => {
        const mid = Number(r.id || 0);
        return `
          <div style="background:#0c0e14; border:1px solid rgba(255,255,255,0.08); border-radius:6px; padding:7px 9px; display:flex; flex-direction:column; gap:4px;">
            <div style="display:flex; justify-content:space-between; align-items:center; gap:6px; flex-wrap:wrap;">
              <span style="color:#f8fafc; font-weight:700;">#${idx + 1} ${escapeHtml(r.topic || 'Memory')} <span style="color:#71717a; font-weight:400;">[${escapeHtml(r.workspace || 'global')}]</span></span>
              <div style="display:flex; align-items:center; gap:5px;">
                <span style="color:#38bdf8;">Cos ${Number(r.neural_cosine || 0).toFixed(2)}</span>
                <span style="color:#ffb020;">Cross ${Number(r.cross_score || 0).toFixed(2)}</span>
                <span style="color:#34d399; font-weight:700;">MLP ${Number(r.mlp_score || 0).toFixed(2)}</span>
                <button type="button" class="tactical-mini-btn" style="padding:1px 6px; border-color:rgba(16,185,129,0.45); color:#6ee7b7;" data-mem-id="${mid}" onclick="sendNeuralPageFeedbackUI(Number(this.dataset.memId), true)">👍 Útil</button>
                <button type="button" class="tactical-mini-btn" style="padding:1px 6px; border-color:rgba(244,63,94,0.45); color:#fda4af;" data-mem-id="${mid}" onclick="sendNeuralPageFeedbackUI(Number(this.dataset.memId), false)">👎 Ruído</button>
              </div>
            </div>
            <div style="color:#a1a1aa; line-height:1.35;">${escapeHtml(String(r.fact || '').slice(0, 220))}</div>
          </div>
        `;
      }).join('');
    }
  } catch (_e) {
    if (outEl) outEl.innerHTML = '<div style="color:#fda4af;">❌ Erro de rede ao executar pesquisa neural.</div>';
  }
}

async function sendNeuralPageFeedbackUI(memoryId, useful) {
  const qEl = document.getElementById('neuralPageQueryInput');
  const query = (qEl ? qEl.value : '').trim();
  try {
    const res = await fetch('/api/v11/neural/feedback', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ memory_id: memoryId, useful: Boolean(useful), query, source: 'neural_studio_page' })
    });
    const data = await res.json();
    if (data && data.ok) {
      if (data.status) neuralPageStatusCache = data.status;
      renderNeuralStudioPage();
      showToast(useful ? '👍 Feedback positivo gravado! Clique em "Treinar MLP Pessoal" para atualizar pesos.' : '👎 Feedback negativo gravado para o próximo treino MLP.');
    }
  } catch (_e) {
    showToast('❌ Erro ao gravar feedback neural');
  }
}

async function runNeuralPageHippoUI() {
  const qEl = document.getElementById('neuralPageCogQueryInput');
  const asEl = document.getElementById('neuralPageAsOfInput');
  const outEl = document.getElementById('neuralPageCogOutput');
  const q = (qEl ? qEl.value : '').trim();
  if (!q) { showToast('Introduza uma query para HippoRAG 2-Hop.'); return; }
  if (outEl) outEl.innerHTML = '<div style="color:#34d399;">🕸️ A correr Personalized PageRank (2-hop HippoRAG)...</div>';
  try {
    const ws = (document.getElementById('neuralPageWsSelect') || {}).value || 'all';
    const asOf = (asEl ? asEl.value : '').trim();
    const res = await fetch(`/api/v10/hipporag?q=${encodeURIComponent(q)}&workspace=${encodeURIComponent(ws)}&hops=2&as_of=${encodeURIComponent(asOf)}`);
    const data = await res.json();
    const rows = Array.isArray(data.results) ? data.results : [];
    if (outEl) {
      outEl.innerHTML = `<div style="color:#94a3b8; font-size:9px; margin-bottom:2px;">⚡ ${Number(data.elapsed_ms || 0).toFixed(1)}ms · Seeds: ${data.seeds_count || 0} · Visitados: ${data.graph_nodes_visited || 0} · Multi-Hop: ${data.multi_hop_discoveries || 0}</div>` + (
        rows.length ? rows.map(r => `
          <div style="background:#0c0e14; border-left:2px solid ${r.is_multi_hop ? '#ff6a00' : '#10b981'}; border-radius:4px; padding:5px 8px;">
            <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:8px;">
              <strong style="color:#f8fafc; min-width:0; word-break:break-word;">${r.is_multi_hop ? '⚡ MULTI-HOP' : '🎯 SEED'} · ${escapeHtml(r.topic || '')}</strong>
              <span style="color:#fbbf24; white-space:nowrap; flex-shrink:0;">PPR ${Number(r.ppr_score || 0).toFixed(3)}</span>
            </div>
            <div style="color:#94a3b8; font-size:8.8px;">${escapeHtml(r.path_reason || '')}</div>
          </div>
        `).join('') : '<div style="color:var(--text-muted);">Sem resultados HippoRAG.</div>'
      );
    }
  } catch (_e) {
    if (outEl) outEl.innerHTML = '<div style="color:#fda4af;">❌ Erro na pesquisa HippoRAG.</div>';
  }
}

async function runNeuralPageTemporalUI() {
  const qEl = document.getElementById('neuralPageCogQueryInput');
  const asEl = document.getElementById('neuralPageAsOfInput');
  const outEl = document.getElementById('neuralPageCogOutput');
  const q = (qEl ? qEl.value : '').trim();
  const asOf = (asEl ? asEl.value : '').trim();
  if (outEl) outEl.innerHTML = '<div style="color:#c084fc;">⏳ A consultar linha temporal Bi-Temporal...</div>';
  try {
    const ws = (document.getElementById('neuralPageWsSelect') || {}).value || 'all';
    const res = await fetch(`/api/v10/temporal?q=${encodeURIComponent(q)}&workspace=${encodeURIComponent(ws)}&as_of=${encodeURIComponent(asOf)}&include_superseded=1&limit=10`);
    const data = await res.json();
    const rows = Array.isArray(data.results) ? data.results : [];
    if (outEl) {
      outEl.innerHTML = `<div style="color:#c084fc; font-size:9px; margin-bottom:2px;">⏳ as_of=${escapeHtml(data.as_of || 'now')} · Ativos: ${data.active_count || 0} · Superseded: ${data.superseded_count || 0}</div>` + (
        rows.length ? rows.map(r => {
          const isSup = Boolean(r.valid_to || r.superseded_by);
          return `
            <div style="background:#0c0e14; border-left:2px solid ${isSup ? '#f59e0b' : '#10b981'}; border-radius:4px; padding:5px 8px; opacity:${isSup ? '0.72' : '1'};">
              <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:8px;">
                <strong style="color:${isSup ? '#fde68a' : '#f8fafc'}; ${isSup ? 'text-decoration:line-through;' : ''} min-width:0; word-break:break-word;">${escapeHtml(r.topic || '')}</strong>
                <span style="color:${isSup ? '#f59e0b' : '#34d399'}; font-size:8.5px; white-space:nowrap; flex-shrink:0;">${isSup ? 'SUPERSEDED ' + escapeHtml(String(r.valid_to || '').slice(0, 10)) : 'ACTIVE'}</span>
              </div>
              <div style="color:#a1a1aa; font-size:9px;">${escapeHtml(String(r.fact || '').slice(0, 160))}</div>
            </div>
          `;
        }).join('') : '<div style="color:var(--text-muted);">Sem factos temporais para este filtro.</div>'
      );
    }
  } catch (_e) {
    if (outEl) outEl.innerHTML = '<div style="color:#fda4af;">❌ Erro na consulta bi-temporal.</div>';
  }
}

async function storeNeuralPageTemporalFactUI() {
  const tEl = document.getElementById('neuralPageTempTopic');
  const fEl = document.getElementById('neuralPageTempFact');
  const topic = (tEl ? tEl.value : '').trim();
  const fact = (fEl ? fEl.value : '').trim();
  if (!topic || !fact) { showToast('Preencha Tópico e Facto para gravar.'); return; }
  const rawWs = (document.getElementById('neuralPageWsSelect') || {}).value || 'brain_mcp';
  const ws = rawWs === 'all' ? 'brain_mcp' : rawWs;
  try {
    const res = await fetch('/api/v10/temporal/store', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ topic, fact, workspace: ws, auto_supersede: true })
    });
    const data = await res.json();
    if (data && data.ok) {
      if (tEl) tEl.value = '';
      if (fEl) fEl.value = '';
      showToast(`💾 Facto bi-temporal gravado (${(data.superseded_ids || []).length} substituído(s))!`);
      fetchNeuralStudioPage();
      fetchGraph();
    } else {
      showToast('❌ Erro ao gravar facto bi-temporal');
    }
  } catch (_e) {
    showToast('❌ Falha de rede ao gravar facto bi-temporal');
  }
}
