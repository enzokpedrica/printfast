import { state } from './state.js?v=2';
import { apiLogin } from './api.js?v=2';
import { getInitials, showToast, closeModal, showLogin, showApp } from './ui.js?v=2';
import { loadDocs, setFilter, setFaseFilter, filterDocs, openFaseModal, selectFaseOption, confirmFaseUpdate, openStatusModal, confirmStatusUpdate } from './rastreio.js?v=2';
import { loadDashboard } from './dashboard.js?v=2';
import { searchProducts, selectProduct, clearSelection, loadPrinters, scanFolder, selectAll, deselectAll, toggleFile, printSelected, confirmPrint } from './impressao.js?v=2';

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
// AUTH
// ============================================
function checkAuth() {
    // Login desativado temporariamente — ative quando quiser
    state.currentUser = { id: 1, nome: 'Usuário Teste', usuario: 'teste' };
    state.authToken   = 'temp';
    _initApp();

    /*
    state.authToken = localStorage.getItem('fastprint_token');
    const userStr   = localStorage.getItem('fastprint_user');
    if (state.authToken && userStr) {
        state.currentUser = JSON.parse(userStr);
        _initApp();
    } else {
        showLogin();
    }
    */
}

function _initApp() {
    showApp(state.currentUser);
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

async function handleLogin(e) {
    e.preventDefault();
    const btn     = document.getElementById('loginBtn');
    const errorEl = document.getElementById('loginError');
    btn.disabled = true;
    btn.textContent = 'Entrando...';
    errorEl.classList.remove('show');

    try {
        const { ok, data } = await apiLogin(
            document.getElementById('loginUsuario').value,
            document.getElementById('loginSenha').value
        );
        if (ok && data.success) {
            state.authToken   = data.token;
            state.currentUser = data.user;
            localStorage.setItem('fastprint_token', state.authToken);
            localStorage.setItem('fastprint_user', JSON.stringify(state.currentUser));
            _initApp();
        } else {
            errorEl.textContent = data.detail || 'Usuário ou senha inválidos';
            errorEl.classList.add('show');
        }
    } catch {
        errorEl.textContent = 'Erro ao conectar com o servidor';
        errorEl.classList.add('show');
    } finally {
        btn.disabled = false;
        btn.textContent = 'Entrar';
    }
}

function handleLogout() {
    if (confirm('Deseja sair do sistema?')) {
        localStorage.removeItem('fastprint_token');
        localStorage.removeItem('fastprint_user');
        state.authToken   = null;
        state.currentUser = null;
        showLogin();
    }
}

// ============================================
// EXPOR FUNÇÕES AO ESCOPO GLOBAL (onclick no HTML)
// ============================================
window.switchTab           = switchTab;
window.handleLogin         = handleLogin;
window.handleLogout        = handleLogout;
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
window.openFaseModal       = openFaseModal;
window.selectFaseOption    = selectFaseOption;
window.confirmFaseUpdate   = confirmFaseUpdate;
window.openStatusModal     = openStatusModal;
window.confirmStatusUpdate = confirmStatusUpdate;

// ============================================
// INIT
// ============================================
document.addEventListener('DOMContentLoaded', checkAuth);
