import { state } from './state.js?v=8';
import { showToast, closeModal } from './ui.js?v=8';
import { loadDocs, setFilter, setFaseFilter, filterDocs, goToPage, changePerPage, openFaseModal, selectFaseOption, confirmFaseUpdate, openStatusModal, confirmStatusUpdate } from './rastreio.js?v=8';
import { loadDashboard } from './dashboard.js?v=6';
import { searchProducts, selectProduct, clearSelection, loadPrinters, scanFolder, selectAll, deselectAll, toggleFile, printSelected, confirmPrint } from './impressao.js?v=8';

// ============================================
// TABS
// ============================================
function switchTab(tab) {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    document.getElementById(`tab-${tab}`).classList.add('active');
    document.getElementById(`panel-${tab}`).classList.add('active');
    if (tab === 'rastreio')  loadDocs();
    if (tab === 'dashboard') loadDashboard();
}

// ============================================
// INIT
// ============================================
function initApp() {
    loadPrinters();
    document.getElementById('folderPath').addEventListener('keypress', e => {
        if (e.key === 'Enter') scanFolder();
    });
    document.getElementById('searchInput').addEventListener('input', e => {
        clearTimeout(state.searchTimeout);
        state.searchTimeout = setTimeout(() => searchProducts(e.target.value), 300);
    });
    loadDocs();
}

// ============================================
// EXPOR FUNÇÕES AO ESCOPO GLOBAL (onclick no HTML)
// ============================================
window.switchTab           = switchTab;
window.closeModal          = closeModal;

// impressao
window.selectProduct       = selectProduct;
window.clearSelection      = clearSelection;
window.scanFolder          = scanFolder;
window.selectAll           = selectAll;
window.deselectAll         = deselectAll;
window.toggleFile          = toggleFile;
window.printSelected       = printSelected;
window.confirmPrint        = confirmPrint;

// rastreio
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

document.addEventListener('DOMContentLoaded', initApp);
