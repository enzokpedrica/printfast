/**
 * App - Módulo Principal da Aplicação
 * 
 * Responsável por:
 * - Inicialização da aplicação ao carregar a página
 * - Navegação entre abas (Impressão, Rastreio, Dashboard)
 * - Exposição de funções ao escopo global (necessário para onclick no HTML)
 */

import { state } from './state.js?v=8';
import { showToast, closeModal } from './ui.js?v=8';
import { loadDocs, setFilter, setFaseFilter, filterDocs, goToPage, changePerPage, openFaseModal, selectFaseOption, confirmFaseUpdate, openStatusModal, confirmStatusUpdate } from './rastreio.js?v=8';
import { loadDashboard } from './dashboard.js?v=6';
import { searchProducts, selectProduct, clearSelection, loadPrinters, scanFolder, selectAll, deselectAll, toggleFile, printSelected, confirmPrint } from './impressao.js?v=8';

// ============================================
// ABAS - Navegação entre as telas do sistema
// ============================================

/** Alterna entre as abas: impressao, rastreio, dashboard */
function switchTab(tab) {
    // Remove 'active' de todas as abas e painéis
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    // Ativa a aba e painel selecionados
    document.getElementById(`tab-${tab}`).classList.add('active');
    document.getElementById(`panel-${tab}`).classList.add('active');
    // Carrega dados específicos da aba ao entrar
    if (tab === 'rastreio')  loadDocs();
    if (tab === 'dashboard') loadDashboard();
}

// ============================================
// INICIALIZAÇÃO
// ============================================

/** Inicializa a aplicação: carrega impressoras, configura listeners e carrega documentos */
function initApp() {
    loadPrinters();
    // Escaneia a pasta ao pressionar Enter no campo de caminho
    document.getElementById('folderPath').addEventListener('keypress', e => {
        if (e.key === 'Enter') scanFolder();
    });
    // Busca de produtos com debounce de 300ms
    document.getElementById('searchInput').addEventListener('input', e => {
        clearTimeout(state.searchTimeout);
        state.searchTimeout = setTimeout(() => searchProducts(e.target.value), 300);
    });
    // Carrega documentos para a tela de rastreio
    loadDocs();
}

// ============================================
// EXPOR FUNÇÕES AO ESCOPO GLOBAL
// Necessário para que os handlers onclick
// definidos diretamente no HTML funcionem.
// ============================================

// Navegação entre abas
window.switchTab           = switchTab;
window.closeModal          = closeModal;

// Funções da tela de impressão
window.selectProduct       = selectProduct;
window.clearSelection      = clearSelection;
window.scanFolder          = scanFolder;
window.selectAll           = selectAll;
window.deselectAll         = deselectAll;
window.toggleFile          = toggleFile;
window.printSelected       = printSelected;
window.confirmPrint        = confirmPrint;

// Funções da tela de rastreio
window.loadDocs            = loadDocs;
window.setFilter           = setFilter;
window.setFaseFilter       = setFaseFilter;
window.filterDocs          = filterDocs;
window.goToPage            = goToPage;
window.changePerPage       = changePerPage;
window.openFaseModal       = openFaseModal;
window.selectFaseOption    = selectFaseOption;
window.confirmFaseUpdate   = confirmFaseUpdate;
window.openStatusModal     = openStatusModal;
window.confirmStatusUpdate = confirmStatusUpdate;

// Inicia a aplicação quando o DOM estiver pronto
document.addEventListener('DOMContentLoaded', initApp);
