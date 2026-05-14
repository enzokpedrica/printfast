import { state } from './state.js?v=8';
import { apiGetDocumentos, apiUpdateStatus, apiUpdateFase } from './api.js?v=8';
import { showToast, closeModal } from './ui.js?v=8';

export async function loadDocs() {
    try {
        const data = await apiGetDocumentos(2000);
        state.allDocs = data.documentos;
        state.currentPage = 1;
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
    state.currentPage       = 1;
    document.querySelectorAll('.filter-tab').forEach(t => t.classList.remove('active'));
    document.getElementById(`f${filter}`).classList.add('active');
    renderDocs();
}

export function setFaseFilter(fase) {
    state.currentFaseFilter = fase;
    state.currentFilter     = 'todos';
    state.currentPage       = 1;
    document.querySelectorAll('.filter-tab').forEach(t => t.classList.remove('active'));
    const ids = { 'Lote Teste': 'ff-teste', 'Lote Piloto': 'ff-piloto', 'Lote Padrão': 'ff-padrao' };
    const el = document.getElementById(ids[fase]);
    if (el) el.classList.add('active');
    renderDocs();
}

export function filterDocs() { state.currentPage = 1; renderDocs(); }

export function goToPage(page) {
    state.currentPage = page;
    renderDocs();
    document.getElementById('docsTableBody').closest('section').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

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

    const totalDocs  = docs.length;
    const totalPages = Math.max(1, Math.ceil(totalDocs / state.perPage));
    if (state.currentPage > totalPages) state.currentPage = totalPages;
    const start = (state.currentPage - 1) * state.perPage;
    const pageDocs = docs.slice(start, start + state.perPage);

    const tbody = document.getElementById('docsTableBody');
    if (totalDocs === 0) {
        tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; padding: 3rem; color: var(--text-muted);">Nenhum documento encontrado</td></tr>`;
        renderPagination(0, 1, 1);
        return;
    }

    renderPagination(totalDocs, state.currentPage, totalPages);

    tbody.innerHTML = pageDocs.map(doc => {
        const statusHtml = {
            entregue: `<span class="status-pill status-entregue">📄 Entregue</span>`,
            recolhido: `<span class="status-pill status-recolhido">📦 Recolhido</span>`,
            baixado:   `<span class="status-pill status-baixado">✅ Baixado</span>`,
        }[doc.status] || doc.status;

        const faseHtml = buildFasePill(doc);
        const data = new Date(doc.impresso_em).toLocaleDateString('pt-BR', {
            day: '2-digit', month: '2-digit', year: '2-digit',
        });


        const tooltip = buildTooltip(doc);

        return `
        <tr title="${tooltip}">
            <td class="mono" style="color: var(--accent);">${doc.codigo_rastreio}</td>
            <td><span class="truncate" title="${doc.produto}">${doc.produto}</span></td>
            <td><span class="truncate" title="${doc.arquivo}" style="font-size:0.8rem; color: var(--text-secondary);">${doc.arquivo}</span></td>
            <td>${faseHtml}</td>
            <td><span class="truncate" style="font-size:0.8rem; color: var(--text-secondary);" title="${doc.computador || ''}">${doc.computador || doc.impresso_por_nome || '—'}</span></td>
            <td style="white-space: nowrap; font-size: 0.8rem; color: var(--text-secondary);">${data}</td>
            <td>${statusHtml}</td>
        </tr>`;
    }).join('');
}

function renderPagination(total, current, totalPages) {
    const el = document.getElementById('docsPagination');
    if (!el) return;

    const start = total === 0 ? 0 : (current - 1) * state.perPage + 1;
    const end   = Math.min(current * state.perPage, total);

    let pages = '';
    const delta = 2;
    for (let i = 1; i <= totalPages; i++) {
        if (i === 1 || i === totalPages || (i >= current - delta && i <= current + delta)) {
            pages += `<button class="page-btn ${i === current ? 'active' : ''}" onclick="goToPage(${i})">${i}</button>`;
        } else if (i === current - delta - 1 || i === current + delta + 1) {
            pages += `<span class="page-ellipsis">…</span>`;
        }
    }

    el.innerHTML = `
        <span class="page-info">${total === 0 ? '0 docs' : `${start}–${end} de ${total}`}</span>
        <div class="page-controls">
            <button class="page-btn" onclick="goToPage(${current - 1})" ${current === 1 ? 'disabled' : ''}>‹</button>
            ${pages}
            <button class="page-btn" onclick="goToPage(${current + 1})" ${current === totalPages ? 'disabled' : ''}>›</button>
        </div>
        <select class="page-size-select" onchange="changePerPage(this.value)">
            ${[25, 50, 100].map(n => `<option value="${n}" ${state.perPage === n ? 'selected' : ''}>${n} por pág.</option>`).join('')}
        </select>`;
}

export function changePerPage(value) {
    state.perPage    = parseInt(value);
    state.currentPage = 1;
    renderDocs();
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
        const data = await apiUpdateFase(state.pendingFaseUpdate.codigo, fase, porProduto);
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
            state.pendingStatusUpdate.novoStatus
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
