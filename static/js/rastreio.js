import { state } from './state.js';
import { apiGetDocumentos, apiUpdateStatus, apiUpdateFase } from './api.js';
import { showToast, closeModal } from './ui.js';

export async function loadDocs() {
    try {
        const data = await apiGetDocumentos(500);
        state.allDocs = data.documentos;
        updateSummary();
        renderDocs();
    } catch {
        showToast('Erro ao carregar documentos', 'error');
    }
}

export function updateSummary() {
    const entregue = state.allDocs.filter(d => d.status === 'entregue').length;
    const baixado  = state.allDocs.filter(d => d.status === 'baixado').length;
    document.getElementById('countEntregue').textContent = entregue;
    document.getElementById('countBaixado').textContent  = baixado;
    document.getElementById('badgeEntregue').textContent = entregue;
}

export function setFilter(filter) {
    state.currentFilter     = filter;
    state.currentFaseFilter = null;
    document.querySelectorAll('.filter-tab').forEach(t => t.classList.remove('active'));
    document.getElementById(`f${filter}`).classList.add('active');
    renderDocs();
}

export function setFaseFilter(fase) {
    state.currentFaseFilter = fase;
    state.currentFilter     = 'todos';
    document.querySelectorAll('.filter-tab').forEach(t => t.classList.remove('active'));
    const ids = { 'Lote Teste': 'ff-teste', 'Lote Piloto': 'ff-piloto', 'Lote Padrão': 'ff-padrao' };
    const el = document.getElementById(ids[fase]);
    if (el) el.classList.add('active');
    renderDocs();
}

export function filterDocs() { renderDocs(); }

export function renderDocs() {
    const search = document.getElementById('trackSearch').value.toLowerCase();
    let docs = state.allDocs;

    if (state.currentFilter !== 'todos') {
        docs = docs.filter(d => d.status === state.currentFilter);
    }
    if (state.currentFaseFilter) {
        docs = docs.filter(d => d.fase === state.currentFaseFilter);
    }
    if (search) {
        docs = docs.filter(d =>
            d.codigo_rastreio.toLowerCase().includes(search) ||
            d.produto.toLowerCase().includes(search) ||
            d.arquivo.toLowerCase().includes(search) ||
            (d.impresso_por_nome || '').toLowerCase().includes(search)
        );
    }

    const tbody = document.getElementById('docsTableBody');
    if (docs.length === 0) {
        tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; padding: 3rem; color: var(--text-muted);">Nenhum documento encontrado</td></tr>`;
        return;
    }

    tbody.innerHTML = docs.map(doc => {
        const statusHtml = {
            entregue: `<span class="status-pill status-entregue">📄 Entregue</span>`,
            recolhido: `<span class="status-pill status-recolhido">📦 Recolhido</span>`,
            baixado:   `<span class="status-pill status-baixado">✅ Baixado</span>`,
        }[doc.status] || doc.status;

        const faseHtml = buildFasePill(doc);
        const data = new Date(doc.impresso_em).toLocaleString('pt-BR', {
            day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit',
        });

        const actionsHtml = doc.status === 'entregue'
            ? `<button class="btn btn-success btn-xs" onclick="openStatusModal('${doc.codigo_rastreio}', 'baixado')">Dar Baixa</button>`
            : `<span style="color: var(--text-muted); font-size: 0.8rem;">—</span>`;

        const tooltip = buildTooltip(doc);

        return `
        <tr title="${tooltip}">
            <td class="mono" style="color: var(--accent);">${doc.codigo_rastreio}</td>
            <td><span class="truncate" title="${doc.produto}">${doc.produto}</span></td>
            <td><span class="truncate" title="${doc.arquivo}" style="font-size:0.8rem; color: var(--text-secondary);">${doc.arquivo}</span></td>
            <td>${faseHtml}</td>
            <td><span class="truncate" style="font-size:0.8rem; color: var(--text-secondary);" title="${doc.impresso_por_nome}${doc.computador ? ' (' + doc.computador + ')' : ''}">${doc.impresso_por_nome || '—'}</span></td>
            <td style="white-space: nowrap; font-size: 0.8rem; color: var(--text-secondary);">${data}</td>
            <td>${statusHtml}</td>
            <td><div class="actions">${actionsHtml}</div></td>
        </tr>`;
    }).join('');
}

function buildTooltip(doc) {
    let tip = `Impresso por: ${doc.impresso_por_nome}`;
    if (doc.computador) tip += ` (${doc.computador})`;
    tip += '\n';
    if (doc.recolhido_por_nome) tip += `Recolhido por: ${doc.recolhido_por_nome} em ${new Date(doc.recolhido_em).toLocaleString('pt-BR')}\n`;
    if (doc.baixado_por_nome)   tip += `Baixado por: ${doc.baixado_por_nome} em ${new Date(doc.baixado_em).toLocaleString('pt-BR')}`;
    return tip;
}

function buildFasePill(doc) {
    const fase    = doc.fase;
    const codEsc  = doc.codigo_rastreio.replace(/'/g, "\\'");
    const prodEsc = (doc.produto || '').replace(/'/g, "\\'").replace(/"/g, '&quot;');
    if (!fase) {
        return `<span class="fase-vazio" onclick="openFaseModal('${codEsc}', '${prodEsc}', '')">+ Fase</span>`;
    }
    const classes = { 'Lote Teste': 'fase-teste', 'Lote Piloto': 'fase-piloto', 'Lote Padrão': 'fase-padrao' };
    const cls = classes[fase] || '';
    return `<span class="fase-pill ${cls}" onclick="openFaseModal('${codEsc}', '${prodEsc}', '${fase}')">${fase}</span>`;
}

// ---- Modal de Fase ----

export function openFaseModal(codigo, produto, faseAtual) {
    state.pendingFaseUpdate = { codigo, produto };
    document.getElementById('faseModalProduto').textContent = produto;
    document.getElementById('faseAplicarTodosLabel').textContent = `todos os documentos do produto "${produto}"`;
    document.getElementById('faseAplicarTodos').checked = false;

    document.querySelectorAll('.fase-option').forEach(el => el.classList.remove('selected'));
    document.querySelectorAll('input[name=faseRadio]').forEach(r => { r.checked = false; });
    if (faseAtual) {
        const radio = document.querySelector(`input[name=faseRadio][value="${faseAtual}"]`);
        if (radio) {
            radio.checked = true;
            radio.closest('.fase-option').classList.add('selected');
        }
    }
    document.getElementById('faseModal').classList.add('show');
}

export function selectFaseOption(valor) {
    document.querySelectorAll('.fase-option').forEach(el => el.classList.remove('selected'));
    const radio = document.querySelector(`input[name=faseRadio][value="${valor}"]`);
    if (radio) {
        radio.checked = true;
        radio.closest('.fase-option').classList.add('selected');
    }
}

export async function confirmFaseUpdate() {
    if (!state.pendingFaseUpdate) return;
    const radio = document.querySelector('input[name=faseRadio]:checked');
    if (!radio) { showToast('Selecione uma fase', 'warning'); return; }

    const fase       = radio.value;
    const porProduto = document.getElementById('faseAplicarTodos').checked;
    closeModal('faseModal');

    try {
        const data = await apiUpdateFase(state.pendingFaseUpdate.codigo, fase, porProduto, state.authToken);
        if (data.success) {
            const msg = porProduto
                ? `Fase "${fase}" aplicada a ${data.affected} documento(s)`
                : `Fase "${fase}" definida`;
            showToast(msg, 'success');
            await loadDocs();
        } else {
            showToast('Erro ao atualizar fase', 'error');
        }
    } catch {
        showToast('Erro ao atualizar fase', 'error');
    } finally {
        state.pendingFaseUpdate = null;
    }
}

// ---- Modal de Status ----

export function openStatusModal(codigo, novoStatus) {
    state.pendingStatusUpdate = { codigo, novoStatus };
    const configs = {
        baixado: { title: 'Dar Baixa no Documento', emoji: '✅', msg: 'Confirma a baixa definitiva deste documento?' },
    };
    const cfg = configs[novoStatus];
    document.getElementById('statusModalTitle').textContent = cfg.title;
    document.getElementById('statusModalEmoji').textContent = cfg.emoji;
    document.getElementById('statusModalMsg').textContent   = cfg.msg;
    document.getElementById('statusModalCodigo').textContent = codigo;
    document.getElementById('statusModal').classList.add('show');
}

export async function confirmStatusUpdate() {
    if (!state.pendingStatusUpdate) return;
    closeModal('statusModal');

    try {
        const data = await apiUpdateStatus(
            state.pendingStatusUpdate.codigo,
            state.pendingStatusUpdate.novoStatus,
            state.authToken
        );
        if (data.success) {
            const labels = { recolhido: 'Documento marcado como recolhido!', baixado: 'Baixa registrada com sucesso!' };
            showToast(labels[state.pendingStatusUpdate.novoStatus], 'success');
            await loadDocs();
        } else {
            showToast('Não foi possível atualizar o status.', 'error');
        }
    } catch {
        showToast('Erro ao atualizar status.', 'error');
    } finally {
        state.pendingStatusUpdate = null;
    }
}
