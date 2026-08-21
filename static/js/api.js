/**
 * API - Camada de comunicação com o backend
 * 
 * Contém wrappers para todas as chamadas fetch (HTTP) ao servidor FastAPI.
 * Centraliza as requisições para facilitar manutenção e tratamento de erros.
 */

/**
 * Busca produtos nas pastas compartilhadas que correspondam à query.
 * Retorna lista de produtos com nome, caminho e quantidade de PDFs.
 */
export async function apiSearch(query) {
    const response = await fetch(`/api/search?query=${encodeURIComponent(query)}`);
    return response.json();
}

/**
 * Obtém a lista de impressoras disponíveis no sistema via CUPS.
 */
export async function apiGetPrinters() {
    const response = await fetch('/api/printers');
    return response.json();
}

/**
 * Envia o caminho de uma pasta e retorna a lista de PDFs encontrados nas subpastas ENG.
 */
export async function apiListPdfs(path) {
    const response = await fetch('/api/list-pdfs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path }),
    });
    if (!response.ok) throw new Error((await response.json()).detail);
    return response.json();
}

/**
 * Envia os PDFs selecionados para impressão.
 * Recebe caminho da pasta, impressora, lista de arquivos e fase de produção.
 */
export async function apiPrint(folder_path, scan_id, printer, selected_files, fase) {
    const response = await fetch('/api/print', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ folder_path, scan_id, printer, selected_files, fase: fase || null }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Erro ao imprimir');
    return data;
}

/**
 * Busca métricas agregadas de todo o histórico para o Dashboard.
 */
export async function apiGetDashboard() {
    const response = await fetch('/api/dashboard');
    if (!response.ok) throw new Error('Erro ao carregar Dashboard');
    return response.json();
}

/**
 * Busca documentos impressos no banco de dados para a tela de rastreio.
 */
export async function apiGetDocumentos(limite = 500) {
    const response = await fetch(`/api/documentos?limite=${limite}`);
    return response.json();
}

/**
 * Atualiza o status de um documento rastreado (ex: entregue → baixado).
 */
export async function apiUpdateStatus(codigo_rastreio, novo_status) {
    const response = await fetch('/api/documentos/status', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ codigo_rastreio, novo_status }),
    });
    return response.json();
}

/**
 * Define ou altera a fase de produção de um documento (Lote Teste, Piloto ou Padrão).
 * Se por_produto=true, aplica a todos os documentos do mesmo produto.
 */
export async function apiUpdateFase(codigo_rastreio, fase, por_produto) {
    const response = await fetch('/api/documentos/fase', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ codigo_rastreio, fase, por_produto }),
    });
    return response.json();
}
