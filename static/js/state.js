// Estado global compartilhado entre módulos
export const state = {
    allDocs: [],
    currentFiles: [],
    currentFilter: 'todos',
    currentFaseFilter: null,
    pendingStatusUpdate: null,
    pendingFaseUpdate: null,
    searchTimeout: null,
    currentPage: 1,
    perPage: 50,
};
