// Gestão de Usuários — página standalone (admin only)

let currentToken = null;
let currentUser  = null;
let currentResetLink = null;

async function init() {
    currentToken = localStorage.getItem('fastprint_token');
    const userStr = localStorage.getItem('fastprint_user');
    if (userStr) currentUser = JSON.parse(userStr);

    if (!currentToken) {
        showError('Faça login no sistema antes de acessar esta página.');
        return;
    }

    try {
        const res = await fetch('/api/users', {
            headers: { 'Authorization': `Bearer ${currentToken}` }
        });

        if (res.status === 401) { showError('Sessão expirada. Faça login novamente.'); return; }
        if (res.status === 403) { showError('Acesso restrito a administradores.'); return; }
        if (!res.ok)            { showError('Erro ao verificar acesso.'); return; }

        document.getElementById('loadingState').style.display = 'none';
        document.getElementById('pageContent').style.display  = 'block';

        if (currentUser) {
            document.getElementById('userName').textContent   = currentUser.nome;
            document.getElementById('userAvatar').textContent = getInitials(currentUser.nome);
        }

        const data = await res.json();
        renderUsers(data.users);

    } catch {
        showError('Erro ao conectar com o servidor.');
    }
}

function showError(msg) {
    document.getElementById('loadingState').style.display = 'none';
    document.getElementById('errorMsg').textContent       = msg;
    document.getElementById('errorState').style.display  = 'block';
}

function getInitials(nome) {
    return nome.split(' ').map(n => n[0]).slice(0, 2).join('').toUpperCase();
}

function renderUsers(users) {
    const tbody = document.getElementById('usersTableBody');
    document.getElementById('userCount').textContent = `${users.length} usuário(s)`;

    if (users.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; padding:2rem; color:var(--text-muted);">Nenhum usuário cadastrado</td></tr>';
        return;
    }

    tbody.innerHTML = users.map(u => {
        const roleBadge = u.role === 'admin'
            ? '<span class="role-badge role-admin">Admin</span>'
            : '<span class="role-badge role-user">Usuário</span>';

        const statusEl = u.ativo
            ? '<span class="status-active">● Ativo</span>'
            : '<span class="status-inactive">○ Inativo</span>';

        const data = u.criado_em
            ? new Date(u.criado_em).toLocaleDateString('pt-BR', { day:'2-digit', month:'2-digit', year:'2-digit' })
            : '—';

        const toggleBtn = u.ativo
            ? `<button class="btn btn-secondary btn-xs" onclick="openToggleModal(${u.id}, '${esc(u.nome)}', true)">Desativar</button>`
            : `<button class="btn btn-secondary btn-xs" onclick="openToggleModal(${u.id}, '${esc(u.nome)}', false)">Ativar</button>`;

        return `
        <tr>
            <td style="color:var(--text-muted); font-size:0.8rem;">${u.id}</td>
            <td><strong>${escHtml(u.nome)}</strong></td>
            <td style="font-family:'JetBrains Mono',monospace; font-size:0.82rem; color:var(--text-secondary);">${escHtml(u.usuario)}</td>
            <td>${roleBadge}</td>
            <td>${statusEl}</td>
            <td style="font-size:0.78rem; color:var(--text-muted);">${data}</td>
            <td>
                <div class="action-btns">
                    <button class="btn btn-secondary btn-xs" onclick="openEditModal(${u.id}, '${esc(u.nome)}', '${u.role}')">Editar</button>
                    <button class="btn btn-secondary btn-xs" onclick="generateResetLink(${u.id})">🔑 Reset</button>
                    ${toggleBtn}
                </div>
            </td>
        </tr>`;
    }).join('');
}

async function loadUsers() {
    try {
        const res  = await fetch('/api/users', { headers: { 'Authorization': `Bearer ${currentToken}` } });
        const data = await res.json();
        renderUsers(data.users);
    } catch {
        showToast('Erro ao carregar usuários', 'error');
    }
}

// ---- Criar ----

window.openCreateModal = function () {
    document.getElementById('createNome').value    = '';
    document.getElementById('createUsuario').value = '';
    document.getElementById('createSenha').value   = '';
    document.getElementById('createRole').value    = 'user';
    setError('createError', '');
    document.getElementById('createModal').classList.add('show');
};

window.submitCreateUser = async function () {
    const nome    = document.getElementById('createNome').value.trim();
    const usuario = document.getElementById('createUsuario').value.trim();
    const senha   = document.getElementById('createSenha').value;
    const role    = document.getElementById('createRole').value;

    if (!nome || !usuario || !senha) { setError('createError', 'Preencha todos os campos'); return; }
    if (senha.length < 8)            { setError('createError', 'Senha deve ter no mínimo 8 caracteres'); return; }

    try {
        const res  = await fetch('/api/users', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${currentToken}` },
            body: JSON.stringify({ nome, usuario, senha, role })
        });
        const data = await res.json();
        if (res.ok && data.success) {
            closeModal('createModal');
            showToast('Usuário criado com sucesso', 'success');
            await loadUsers();
        } else {
            setError('createError', data.detail || 'Erro ao criar usuário');
        }
    } catch { setError('createError', 'Erro de conexão'); }
};

// ---- Editar ----

window.openEditModal = function (id, nome, role) {
    document.getElementById('editUserId').value = id;
    document.getElementById('editNome').value   = nome;
    document.getElementById('editRole').value   = role;
    setError('editError', '');
    document.getElementById('editModal').classList.add('show');
};

window.submitEditUser = async function () {
    const id   = document.getElementById('editUserId').value;
    const nome = document.getElementById('editNome').value.trim();
    const role = document.getElementById('editRole').value;

    if (!nome) { setError('editError', 'Nome não pode ser vazio'); return; }

    try {
        const res  = await fetch(`/api/users/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${currentToken}` },
            body: JSON.stringify({ nome, role })
        });
        const data = await res.json();
        if (res.ok && data.success) {
            closeModal('editModal');
            showToast('Usuário atualizado', 'success');
            await loadUsers();
        } else {
            setError('editError', data.detail || 'Erro ao atualizar');
        }
    } catch { setError('editError', 'Erro de conexão'); }
};

// ---- Link de Reset ----

window.generateResetLink = async function (userId) {
    try {
        const res  = await fetch(`/api/users/${userId}/reset-link`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${currentToken}` }
        });
        const data = await res.json();
        if (res.ok && data.success) {
            currentResetLink = `${window.location.origin}/reset-password?token=${data.token}`;
            document.getElementById('resetLinkUrl').textContent = currentResetLink;
            document.getElementById('resetLinkModal').classList.add('show');
        } else {
            showToast(data.detail || 'Erro ao gerar link', 'error');
        }
    } catch { showToast('Erro de conexão', 'error'); }
};

window.copyResetLink = function () {
    if (!currentResetLink) return;
    navigator.clipboard.writeText(currentResetLink)
        .then(() => showToast('Link copiado!', 'success'))
        .catch(() => showToast('Selecione e copie o link manualmente', 'warning'));
};

// ---- Ativar / Desativar ----

window.openToggleModal = function (id, nome, isActive) {
    document.getElementById('toggleUserId').value    = id;
    document.getElementById('toggleAtivoValue').value = isActive ? '0' : '1';
    document.getElementById('toggleIcon').textContent  = isActive ? '⚠️' : '✅';
    document.getElementById('toggleTitle').textContent = isActive ? 'Desativar Usuário' : 'Ativar Usuário';
    document.getElementById('toggleMsg').textContent   = isActive
        ? `Deseja desativar "${nome}"? Ele não conseguirá mais fazer login.`
        : `Deseja reativar "${nome}"?`;
    document.getElementById('toggleConfirmBtn').textContent = isActive ? 'Desativar' : 'Ativar';
    document.getElementById('toggleModal').classList.add('show');
};

window.submitToggleUser = async function () {
    const id    = document.getElementById('toggleUserId').value;
    const ativo = parseInt(document.getElementById('toggleAtivoValue').value);
    closeModal('toggleModal');

    try {
        let res;
        if (ativo === 0) {
            res = await fetch(`/api/users/${id}`, {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${currentToken}` }
            });
        } else {
            res = await fetch(`/api/users/${id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${currentToken}` },
                body: JSON.stringify({ ativo: 1 })
            });
        }
        const data = await res.json();
        if (res.ok && data.success) {
            showToast(ativo === 0 ? 'Usuário desativado' : 'Usuário ativado', 'success');
            await loadUsers();
        } else {
            showToast(data.detail || 'Erro ao alterar status', 'error');
        }
    } catch { showToast('Erro de conexão', 'error'); }
};

// ---- Utilitários ----

window.closeModal = function (id) {
    document.getElementById(id).classList.remove('show');
};

function setError(elId, msg) {
    const el = document.getElementById(elId);
    el.textContent    = msg;
    el.style.display  = msg ? 'block' : 'none';
}

function showToast(msg, type = 'success') {
    const container = document.getElementById('toastContainer');
    const toast     = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `<span>${{ success: '✓', error: '✗', warning: '⚠' }[type]}</span> ${msg}`;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.animation = 'slideIn 0.3s ease reverse';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

function escHtml(str) {
    return String(str)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;')
        .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function esc(str) {
    return String(str).replace(/'/g, "\\'").replace(/\\/g, '\\\\');
}

document.addEventListener('DOMContentLoaded', init);
