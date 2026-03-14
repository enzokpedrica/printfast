import { state } from './state.js';
import { apiGetDocumentos } from './api.js';
import { showToast } from './ui.js';
import { updateSummary } from './rastreio.js';

export async function loadDashboard() {
    if (state.allDocs.length === 0) {
        try {
            const data = await apiGetDocumentos(500);
            state.allDocs = data.documentos;
            updateSummary();
        } catch {
            showToast('Erro ao carregar dados', 'error');
            return;
        }
    }
    renderDashboard();
}

export function renderDashboard() {
    const docs     = state.allDocs;
    const total    = docs.length;
    const entregues = docs.filter(d => d.status === 'entregue').length;
    const baixados  = docs.filter(d => d.status === 'baixado').length;
    const semFase   = docs.filter(d => !d.fase).length;
    const taxa      = total > 0 ? Math.round((baixados / total) * 100) : 0;

    document.getElementById('dTotalDocs').textContent = total;
    document.getElementById('dTotalSub').textContent  = total === 1 ? 'documento' : 'documentos';
    document.getElementById('dEntregues').textContent = entregues;
    document.getElementById('dBaixados').textContent  = baixados;
    document.getElementById('dTaxa').textContent      = `${taxa}%`;
    document.getElementById('dSemFase').textContent   = semFase;

    // --- Fase bars ---
    const faseCounts = {
        'Lote Teste':  docs.filter(d => d.fase === 'Lote Teste').length,
        'Lote Piloto': docs.filter(d => d.fase === 'Lote Piloto').length,
        'Lote Padrão': docs.filter(d => d.fase === 'Lote Padrão').length,
        'Sem fase':    semFase,
    };
    const maxFase    = Math.max(...Object.values(faseCounts), 1);
    const faseClasses = {
        'Lote Teste': 'fase-teste', 'Lote Piloto': 'fase-piloto',
        'Lote Padrão': 'fase-padrao', 'Sem fase': 'bar-semfase',
    };
    document.getElementById('dashFaseBars').innerHTML = Object.entries(faseCounts).map(([nome, qtd]) => `
        <div class="bar-row">
            <div class="bar-meta"><span class="bar-name">${nome}</span><span class="bar-num">${qtd}</span></div>
            <div class="bar-track"><div class="bar-fill ${faseClasses[nome]}" style="width:${Math.round((qtd / maxFase) * 100)}%"></div></div>
        </div>
    `).join('');

    // --- Top produtos ---
    const prodMap = {};
    docs.forEach(d => {
        if (!prodMap[d.produto]) prodMap[d.produto] = { total: 0, entregue: 0, baixado: 0 };
        prodMap[d.produto].total++;
        if (d.status === 'entregue') prodMap[d.produto].entregue++;
        if (d.status === 'baixado')  prodMap[d.produto].baixado++;
    });
    const topProdutos = Object.entries(prodMap).sort((a, b) => b[1].total - a[1].total).slice(0, 10);

    document.getElementById('dashProdutosBody').innerHTML = topProdutos.length === 0
        ? `<tr><td colspan="4" class="dash-empty">Sem dados</td></tr>`
        : topProdutos.map(([nome, c]) => `
            <tr>
                <td class="td-produto" title="${nome}" style="max-width:200px;">${nome}</td>
                <td class="td-num">${c.total}</td>
                <td class="td-num" style="color:var(--info);">${c.entregue}</td>
                <td class="td-num" style="color:var(--success);">${c.baixado}</td>
            </tr>
        `).join('');

    // --- Usuários ---
    const userMap = {};
    docs.forEach(d => {
        const u = d.impresso_por_nome || 'Desconhecido';
        userMap[u] = (userMap[u] || 0) + 1;
    });
    const topUsers = Object.entries(userMap).sort((a, b) => b[1] - a[1]).slice(0, 8);
    const maxUser  = topUsers[0]?.[1] || 1;
    document.getElementById('dashUsuarioBars').innerHTML = topUsers.length === 0
        ? '<div class="dash-empty">Sem dados</div>'
        : topUsers.map(([nome, qtd]) => `
            <div class="bar-row">
                <div class="bar-meta"><span class="bar-name">${nome}</span><span class="bar-num">${qtd}</span></div>
                <div class="bar-track"><div class="bar-fill bar-accent" style="width:${Math.round((qtd / maxUser) * 100)}%"></div></div>
            </div>
        `).join('');

    // --- Recentes ---
    const recentes = [...docs].sort((a, b) => new Date(b.impresso_em) - new Date(a.impresso_em)).slice(0, 10);
    const statusIcons = {
        entregue: `<span class="status-pill status-entregue" style="font-size:0.7rem; padding:0.15rem 0.5rem;">Entregue</span>`,
        baixado:  `<span class="status-pill status-baixado" style="font-size:0.7rem; padding:0.15rem 0.5rem;">Baixado</span>`,
    };
    document.getElementById('dashRecenteBody').innerHTML = recentes.length === 0
        ? `<tr><td colspan="4" class="dash-empty">Sem dados</td></tr>`
        : recentes.map(d => {
            const dt = new Date(d.impresso_em).toLocaleString('pt-BR', {
                day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
            });
            return `<tr>
                <td class="td-produto" title="${d.produto}" style="max-width:160px;">${d.produto}</td>
                <td class="td-produto" title="${d.arquivo}" style="max-width:160px; color:var(--text-secondary); font-size:0.78rem;">${d.arquivo}</td>
                <td style="white-space:nowrap; font-size:0.78rem; color:var(--text-secondary);">${dt}</td>
                <td class="td-badge">${statusIcons[d.status] || d.status}</td>
            </tr>`;
        }).join('');
}
