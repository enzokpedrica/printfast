// Estado global compartilhado entre módulos
export const state = {
    authToken: null,
    currentUser: null,
    allDocs: [],
    currentFiles: [],
    currentFilter: 'todos',
    currentFaseFilter: null,
    pendingStatusUpdate: null,
    pendingFaseUpdate: null,
    searchTimeout: null,
};
