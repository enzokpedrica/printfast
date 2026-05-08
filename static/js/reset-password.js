// Página de reset de senha — recebe ?token=xxx na URL

const params = new URLSearchParams(window.location.search);
const token  = params.get('token');

const STATES = ['stateLoading', 'stateInvalid', 'stateForm', 'stateSuccess'];

function showState(active) {
    STATES.forEach(id => {
        document.getElementById(id).style.display = id === active ? 'block' : 'none';
    });
}

async function init() {
    if (!token) {
        document.getElementById('invalidMsg').textContent = 'Link inválido: token não encontrado na URL';
        showState('stateInvalid');
        return;
    }

    try {
        const res  = await fetch(`/api/auth/validate-reset-token?token=${encodeURIComponent(token)}`);
        const data = await res.json();
        if (data.valid) {
            document.getElementById('greetingName').textContent = data.nome;
            showState('stateForm');
        } else {
            document.getElementById('invalidMsg').textContent = data.reason || 'Link inválido ou expirado';
            showState('stateInvalid');
        }
    } catch {
        document.getElementById('invalidMsg').textContent = 'Erro ao verificar o link. Tente novamente.';
        showState('stateInvalid');
    }
}

window.submitReset = async function (e) {
    e.preventDefault();
    const novaSenha   = document.getElementById('novaSenha').value;
    const confirmar   = document.getElementById('confirmarSenha').value;
    const errEl       = document.getElementById('formError');
    const btn         = document.getElementById('submitBtn');

    errEl.classList.remove('show');

    if (novaSenha !== confirmar) {
        errEl.textContent = 'As senhas não coincidem';
        errEl.classList.add('show');
        return;
    }
    if (novaSenha.length < 8) {
        errEl.textContent = 'Senha deve ter no mínimo 8 caracteres';
        errEl.classList.add('show');
        return;
    }

    btn.disabled    = true;
    btn.textContent = 'Redefinindo...';

    try {
        const res  = await fetch('/api/auth/reset-password', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ token, nova_senha: novaSenha })
        });
        const data = await res.json();
        if (res.ok && data.success) {
            showState('stateSuccess');
        } else {
            errEl.textContent = data.detail || 'Erro ao redefinir senha';
            errEl.classList.add('show');
            btn.disabled    = false;
            btn.textContent = 'Redefinir Senha';
        }
    } catch {
        errEl.textContent = 'Erro de conexão com o servidor';
        errEl.classList.add('show');
        btn.disabled    = false;
        btn.textContent = 'Redefinir Senha';
    }
};

document.addEventListener('DOMContentLoaded', init);
