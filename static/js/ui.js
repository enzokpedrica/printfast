/**
 * UI - Utilitários de Interface
 * 
 * Funções auxiliares para manipulação do DOM:
 * - Exibição de notificações toast (sucesso, erro, aviso)
 * - Abertura e fechamento de modais
 */

/**
 * Exibe uma notificação toast temporária no canto da tela.
 * Tipos: 'success' (verde), 'error' (vermelho), 'warning' (amarelo).
 */
export function showToast(msg, type = 'success') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `<span>${{ success: '✓', error: '✗', warning: '⚠' }[type]}</span> ${msg}`;
    container.appendChild(toast);
    // Remove o toast automaticamente após 4 segundos
    setTimeout(() => {
        toast.style.animation = 'slideIn 0.3s ease reverse';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

/**
 * Fecha um modal removendo a classe 'show' do overlay.
 */
export function closeModal(id) {
    document.getElementById(id).classList.remove('show');
}
