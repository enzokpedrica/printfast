/**
 * Estado Global da Aplicação
 * 
 * Objeto compartilhado entre todos os módulos JS.
 * Armazena dados carregados do servidor e estado da interface.
 */
export const state = {
    allDocs: [],              // Todos os documentos carregados do banco (rastreio)
    currentFiles: [],         // PDFs encontrados na pasta atual (tela de impressão)
    currentScanId: null,       // Token temporário da última varredura autorizada
    currentFilter: 'todos',   // Filtro de status ativo na tela de rastreio
    currentFaseFilter: null,  // Filtro de fase ativo na tela de rastreio
    pendingStatusUpdate: null, // Dados da atualização de status pendente (modal)
    pendingFaseUpdate: null,   // Dados da atualização de fase pendente (modal)
    searchTimeout: null,       // Timer do debounce da busca de produtos
    currentPage: 1,            // Página atual da tabela de rastreio
    perPage: 50,               // Quantidade de documentos por página
};
