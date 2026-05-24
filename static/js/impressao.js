/**
 * Impressão - Módulo da tela de impressão de PDFs
 * 
 * Gerencia todo o fluxo de impressão:
 * - Busca de produtos nas pastas compartilhadas
 * - Seleção de produto e escaneamento de PDFs
 * - Seleção/desseleção de arquivos individuais
 * - Envio dos PDFs selecionados para a impressora
 * - Acompanhamento do progresso de impressão
 */

import { state } from './state.js?v=8';
import { apiSearch, apiGetPrinters, apiListPdfs, apiPrint } from './api.js?v=8';
import { showToast, closeModal } from './ui.js?v=8';
import { loadDocs } from './rastreio.js?v=8';

/**
 * Busca produtos nas pastas compartilhadas que correspondam ao texto digitado.
 * Exibe os resultados como cards clicáveis na área de busca.
 */
export async function searchProducts(query) {
    const container = document.getElementById('searchResults');
    if (!query || query.length < 3) { container.innerHTML = ''; return; }
    container.innerHTML = '<div class="loading"><div class="spinner"></div>Buscando...</div>';
    try {
        const data = await apiSearch(query);
        if (data.results.length === 0) {
            container.innerHTML = `<div style="padding: 1rem; color: var(--text-secondary); text-align: center;">Nenhum produto encontrado</div>`;
            return;
        }
        container.innerHTML = data.results.map(p => `
            <div class="search-result-item" onclick="selectProduct('${p.path.replace(/\\/g, '\\\\')}', '${p.name}')">
                <div class="search-result-info"><h4>${p.name}</h4><span>${p.path}</span></div>
                <div class="search-result-meta">
                    <div class="pdf-count">${p.pdf_count} PDFs</div>
                    <div class="status">${p.status}</div>
                </div>
            </div>
        `).join('');
    } catch {
        container.innerHTML = `<div style="padding: 1rem; color: var(--error);">Erro ao buscar</div>`;
    }
}

/**
 * Seleciona um produto da busca: preenche o campo de caminho e inicia o escaneamento.
 */
export function selectProduct(path, name) {
    document.getElementById('folderPath').value = path;
    document.getElementById('searchInput').value = '';
    document.getElementById('searchResults').innerHTML = '';
    document.getElementById('selectedProduct').style.display = 'flex';
    document.getElementById('selectedProductName').textContent = name;
    document.getElementById('selectedProductPath').textContent = path;
    scanFolder();
}

/**
 * Limpa a seleção atual de produto e volta ao estado inicial.
 */
export function clearSelection() {
    document.getElementById('folderPath').value = '';
    document.getElementById('selectedProduct').style.display = 'none';
    document.getElementById('resultsSection').style.display = 'none';
    document.getElementById('emptyState').style.display = 'block';
    state.currentFiles = [];
}

/**
 * Carrega as impressoras disponíveis do sistema e popula o select na interface.
 */
export async function loadPrinters() {
    try {
        const data = await apiGetPrinters();
        const select = document.getElementById('printerSelect');
        select.innerHTML = '';
        data.printers.forEach(printer => {
            const option = document.createElement('option');
            option.value = printer;
            option.textContent = printer;
            select.appendChild(option);
        });
    } catch {
        showToast('Erro ao carregar impressoras', 'error');
    }
}

/**
 * Escaneia a pasta informada e lista todos os PDFs encontrados nas subpastas ENG.
 * Todos os arquivos iniciam selecionados por padrão.
 */
export async function scanFolder() {
    const path = document.getElementById('folderPath').value.trim();
    if (!path) { showToast('Digite o caminho da pasta', 'warning'); return; }
    document.getElementById('emptyState').style.display = 'none';
    document.getElementById('resultsSection').style.display = 'block';
    document.getElementById('fileList').innerHTML = '<div class="loading"><div class="spinner"></div>Escaneando...</div>';
    try {
        const data = await apiListPdfs(path);
        state.currentFiles = data.files.map(f => ({ ...f, selected: true }));
        renderFiles();
        updateCounts();
        showToast(`${data.total} arquivos encontrados`, data.total > 0 ? 'success' : 'warning');
    } catch (error) {
        showToast(error.message, 'error');
        document.getElementById('fileList').innerHTML = `<div class="empty-state"><div class="empty-state-icon">❌</div><h3>Erro ao escanear</h3><p>${error.message}</p></div>`;
    }
}

/**
 * Renderiza a lista de PDFs encontrados como itens com checkbox.
 */
export function renderFiles() {
    const container = document.getElementById('fileList');
    if (state.currentFiles.length === 0) {
        container.innerHTML = `<div class="empty-state"><div class="empty-state-icon">📭</div><h3>Nenhum PDF encontrado</h3><p>Não há PDFs nas pastas ENG</p></div>`;
        return;
    }
    container.innerHTML = state.currentFiles.map((file, i) => `
        <div class="file-item" id="file-${i}">
            <input type="checkbox" class="file-checkbox" ${file.selected ? 'checked' : ''} onchange="toggleFile(${i})">
            <div class="file-icon">PDF</div>
            <div class="file-info">
                <div class="file-name">${file.name}</div>
                <div class="file-meta"><span class="folder-badge">${file.folder}</span><span>${file.size_kb} KB</span></div>
            </div>
            <div class="file-status pending" id="status-${i}">⏳</div>
        </div>
    `).join('');
}

/** Alterna a seleção de um arquivo individual pelo índice. */
export function toggleFile(i) {
    state.currentFiles[i].selected = !state.currentFiles[i].selected;
    updateCounts();
}

/** Seleciona todos os PDFs da lista. */
export function selectAll() {
    state.currentFiles.forEach(f => f.selected = true);
    renderFiles();
    updateCounts();
}

/** Desmarca todos os PDFs da lista. */
export function deselectAll() {
    state.currentFiles.forEach(f => f.selected = false);
    renderFiles();
    updateCounts();
}

/** Atualiza os contadores de arquivos selecionados e o texto do botão de imprimir. */
export function updateCounts() {
    const selected = state.currentFiles.filter(f => f.selected).length;
    const total    = state.currentFiles.length;
    document.getElementById('fileCount').textContent    = `${total} PDFs`;
    document.getElementById('totalFiles').textContent   = total;
    document.getElementById('selectedCount').textContent = selected;
    const btn = document.getElementById('printBtn');
    btn.disabled    = selected === 0;
    btn.textContent = selected === total ? '🖨️ Imprimir Todos' : `🖨️ Imprimir ${selected} Selecionados`;
}

/**
 * Abre o modal de confirmação de impressão com resumo do produto, impressora e arquivos.
 * O usuário pode opcionalmente selecionar a fase de produção antes de confirmar.
 */
export function printSelected() {
    const selected = state.currentFiles.filter(f => f.selected);
    if (selected.length === 0) { showToast('Selecione pelo menos um arquivo', 'warning'); return; }
    const path      = document.getElementById('folderPath').value.trim();
    const produto   = path.split('\\').pop() || path.split('/').pop() || 'Produto';
    const printer   = document.getElementById('printerSelect');
    const impressora = printer.options[printer.selectedIndex].text || 'Padrão do Sistema';
    document.getElementById('modalProduto').textContent   = produto;
    document.getElementById('modalImpressora').textContent = impressora;
    document.getElementById('modalArquivos').textContent   = `${selected.length} arquivo(s)`;
    document.getElementById('modalFase').value = '';
    document.getElementById('confirmModal').classList.add('show');
}

/**
 * Confirma a impressão: envia os PDFs selecionados ao backend.
 * Atualiza o progresso visual e exibe o resultado (sucesso/falha por arquivo).
 */
export async function confirmPrint() {
    closeModal('confirmModal');
    const selected = state.currentFiles.filter(f => f.selected);
    const path     = document.getElementById('folderPath').value.trim();
    const printer  = document.getElementById('printerSelect').value || null;
    const fase     = document.getElementById('modalFase').value || null;
    const btn      = document.getElementById('printBtn');
    btn.disabled   = true;
    btn.innerHTML  = '⏳ Imprimindo...';
    document.getElementById('progressContainer').classList.add('active');

    try {
        const data = await apiPrint(path, printer, selected.map(f => f.path), fase);
        let idx = 0;
        state.currentFiles.forEach((file, i) => {
            if (file.selected && data.results[idx]) {
                const el = document.getElementById(`status-${i}`);
                el.className = `file-status ${data.results[idx].success ? 'success' : 'error'}`;
                el.textContent = data.results[idx].success ? '✓' : '✗';
                idx++;
                const pct = Math.round((idx / data.total) * 100);
                document.getElementById('progressFill').style.width = `${pct}%`;
                document.getElementById('progressPercent').textContent = `${pct}%`;
            }
        });
        document.getElementById('progressText').textContent = 'Concluído!';
        showToast(
            `${data.printed}/${data.total} impressos! Documentos registrados no rastreio.`,
            data.printed === data.total ? 'success' : 'warning'
        );
        setTimeout(loadDocs, 1000);
    } catch (error) {
        showToast('Erro: ' + error.message, 'error');
    } finally {
        btn.disabled = false;
        updateCounts();
    }
}
