// Utilitários de DOM: toasts, modais

export function showToast(msg, type = 'success') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `<span>${{ success: '✓', error: '✗', warning: '⚠' }[type]}</span> ${msg}`;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.animation = 'slideIn 0.3s ease reverse';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

export function closeModal(id) {
    document.getElementById(id).classList.remove('show');
}
