// Wrappers de chamadas fetch para o backend

export async function apiSearch(query) {
    const response = await fetch(`/api/search?query=${encodeURIComponent(query)}`);
    return response.json();
}

export async function apiGetPrinters() {
    const response = await fetch('/api/printers');
    return response.json();
}

export async function apiListPdfs(path) {
    const response = await fetch('/api/list-pdfs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path }),
    });
    if (!response.ok) throw new Error((await response.json()).detail);
    return response.json();
}

export async function apiPrint(folder_path, printer, selected_files, token, fase) {
    const response = await fetch('/api/print', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ folder_path, printer, selected_files, fase: fase || null }),
    });
    return response.json();
}

export async function apiLogin(usuario, senha) {
    const response = await fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ usuario, senha }),
    });
    return { ok: response.ok, data: await response.json() };
}

export async function apiGetDocumentos(limite = 500) {
    const response = await fetch(`/api/documentos?limite=${limite}`);
    return response.json();
}

export async function apiUpdateStatus(codigo_rastreio, novo_status, token) {
    const response = await fetch('/api/documentos/status', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ codigo_rastreio, novo_status }),
    });
    return response.json();
}

export async function apiUpdateFase(codigo_rastreio, fase, por_produto, token) {
    const response = await fetch('/api/documentos/fase', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ codigo_rastreio, fase, por_produto }),
    });
    return response.json();
}
