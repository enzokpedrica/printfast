// Utilitários de DOM: toasts, modais, iniciais

export function getInitials(nome) {
    return nome.split(' ').map(n => n[0]).slice(0, 2).join('').toUpperCase();
}

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

export function showLogin() {
    document.getElementById('loginScreen').style.display = 'flex';
    document.getElementById('appContainer').style.display = 'none';
}

export function showApp(user) {
    document.getElementById('loginScreen').style.display = 'none';
    document.getElementById('appContainer').style.display = 'block';
    document.getElementById('userName').textContent = user.nome;
    document.getElementById('userAvatar').textContent = getInitials(user.nome);
}
