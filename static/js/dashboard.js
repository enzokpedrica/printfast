/**
 * Dashboard - Painel de indicadores e estatísticas agregadas.
 */

import { apiGetDashboard } from './api.js?v=8';
import { showToast } from './ui.js?v=8';

export async function loadDashboard() {
    try {
        const data = await apiGetDashboard();
        renderDashboard(data);
    } catch {
        showToast('Erro ao carregar dados do Dashboard', 'error');
    }
}

export function renderDashboard(data) {
    const resumo = data.resumo;
    const total = resumo.total;
    const taxa = Number(resumo.taxa_baixa || 0).toFixed(1).replace('.', ',');

    document.getElementById('dTotalDocs').textContent = total;
    document.getElementById('dTotalSub').textContent = total === 1 ? 'documento' : 'documentos';
    document.getElementById('dEntregues').textContent = resumo.entregues;
    document.getElementById('dBaixados').textContent = resumo.baixados;
    document.getElementById('dTaxa').textContent = `${taxa}%`;
    document.getElementById('dSemFase').textContent = resumo.sem_fase;

    const formatDate = value => value
        ? new Date(value).toLocaleDateString('pt-BR')
        : '—';
    document.getElementById('dashPeriodo').textContent =
        total > 0
            ? `Todo o histórico: ${formatDate(data.periodo.inicio)} a ${formatDate(data.periodo.fim)}`
            : 'Todo o histórico: sem dados';

    const faseCounts = {
        'Lote Teste': data.fases['Lote Teste'] || 0,
        'Lote Piloto': data.fases['Lote Piloto'] || 0,
        'Lote Padrão': data.fases['Lote Padrão'] || 0,
        'Sem fase': data.fases['Sem fase'] || 0,
    };
    const maxFase = Math.max(...Object.values(faseCounts), 1);
    const faseClasses = {
        'Lote Teste': 'fase-teste',
        'Lote Piloto': 'fase-piloto',
        'Lote Padrão': 'fase-padrao',
        'Sem fase': 'bar-semfase',
    };
    document.getElementById('dashFaseBars').innerHTML = Object.entries(faseCounts).map(([nome, qtd]) => `
        <div class="bar-row">
            <div class="bar-meta"><span class="bar-name">${nome}</span><span class="bar-num">${qtd}</span></div>
            <div class="bar-track"><div class="bar-fill ${faseClasses[nome]}" style="width:${Math.round((qtd / maxFase) * 100)}%"></div></div>
        </div>
    `).join('');

    document.getElementById('dashProdutosBody').innerHTML = data.top_produtos.length === 0
        ? '<tr><td colspan="4" class="dash-empty">Sem dados</td></tr>'
        : data.top_produtos.map(item => `
            <tr>
                <td class="td-produto" title="${item.produto}" style="max-width:200px;">${item.produto}</td>
                <td class="td-num">${item.total}</td>
                <td class="td-num" style="color:var(--info);">${item.entregues}</td>
                <td class="td-num" style="color:var(--success);">${item.baixados}</td>
            </tr>
        `).join('');

    const maxComputador = data.computadores[0]?.total || 1;
    document.getElementById('dashUsuarioBars').innerHTML = data.computadores.length === 0
        ? '<div class="dash-empty">Sem dados</div>'
        : data.computadores.map(item => `
            <div class="bar-row">
                <div class="bar-meta"><span class="bar-name">${item.computador}</span><span class="bar-num">${item.total}</span></div>
                <div class="bar-track"><div class="bar-fill bar-accent" style="width:${Math.round((item.total / maxComputador) * 100)}%"></div></div>
            </div>
        `).join('');

    const statusHtml = {
        entregue: '<span class="status-pill status-entregue" style="font-size:0.7rem; padding:0.15rem 0.5rem;">Entregue</span>',
        baixado: '<span class="status-pill status-baixado" style="font-size:0.7rem; padding:0.15rem 0.5rem;">Baixado</span>',
    };
    document.getElementById('dashRecenteBody').innerHTML = data.recentes.length === 0
        ? '<tr><td colspan="4" class="dash-empty">Sem dados</td></tr>'
        : data.recentes.map(item => {
            const dt = new Date(item.impresso_em).toLocaleString('pt-BR', {
                day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
            });
            return `<tr>
                <td class="td-produto" title="${item.produto}" style="max-width:160px;">${item.produto}</td>
                <td class="td-produto" title="${item.arquivo}" style="max-width:160px; color:var(--text-secondary); font-size:0.78rem;">${item.arquivo}</td>
                <td style="white-space:nowrap; font-size:0.78rem; color:var(--text-secondary);">${dt}</td>
                <td class="td-badge">${statusHtml[item.status] || item.status}</td>
            </tr>`;
        }).join('');
}
