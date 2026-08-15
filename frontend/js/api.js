/* Banking Legal Platform — API client
   Communicates with the Platform API (Task 014).
   All operations go through this module; the UI never calls backend services directly. */

const API_BASE = '/api';

class ApiClient {
  constructor() {
    this.token = localStorage.getItem('auth_token') || null;
  }

  setToken(token) {
    this.token = token;
    if (token) {
      localStorage.setItem('auth_token', token);
    } else {
      localStorage.removeItem('auth_token');
    }
  }

  async request(method, path, body = null, params = {}) {
    const url = new URL(API_BASE + path, window.location.origin);
    for (const [k, v] of Object.entries(params)) {
      if (v !== null && v !== undefined && v !== '') url.searchParams.set(k, v);
    }

    const headers = { 'Content-Type': 'application/json' };
    if (this.token) headers['Authorization'] = `Bearer ${this.token}`;

    const opts = { method, headers };
    if (body !== null) opts.body = JSON.stringify(body);

    try {
      const resp = await fetch(url.toString(), opts);
      const data = await resp.json();
      return data;
    } catch (err) {
      return {
        success: false,
        status: 0,
        error: { code: 'NETWORK_ERROR', message: `Network error: ${err.message}`, category: 'INTERNAL' },
        request_id: 'error',
        timestamp: new Date().toISOString()
      };
    }
  }

  get(path, params = {}) { return this.request('GET', path, null, params); }
  post(path, body = {}) { return this.request('POST', path, body); }
  patch(path, body = {}) { return this.request('PATCH', path, body); }
  del(path) { return this.request('DELETE', path); }

  // --- Auth ---
  async login(user_id, password) {
    const resp = await this.post('/v1/auth/login', { user_id, password });
    if (resp.success) this.setToken(resp.data.token);
    return resp;
  }
  logout() {
    this.post('/v1/auth/logout');
    this.setToken(null);
  }
  async me() { return this.get('/v1/auth/me'); }

  // --- Health ---
  async health() { return this.get('/health'); }
  async ready() { return this.get('/ready'); }

  // --- Vaults ---
  async listVaults(params = {}) { return this.get('/v1/vaults', params); }
  async getVault(id) { return this.get(`/v1/vaults/${id}`); }
  async createVault(body) { return this.post('/v1/vaults', body); }
  async updateVault(id, body) { return this.patch(`/v1/vaults/${id}`, body); }
  async deleteVault(id) { return this.del(`/v1/vaults/${id}`); }

  // --- Documents ---
  async listDocuments(params = {}) { return this.get('/v1/documents', params); }
  async getDocument(id) { return this.get(`/v1/documents/${id}`); }
  async createDocument(body) { return this.post('/v1/documents', body); }
  async updateDocument(id, body) { return this.patch(`/v1/documents/${id}`, body); }
  async deleteDocument(id) { return this.del(`/v1/documents/${id}`); }
  async getDocumentStatus(id) { return this.get(`/v1/documents/${id}/status`); }
  async getDocumentSource(id, params = {}) { return this.get(`/v1/documents/${id}/source`, params); }

  // --- Uploads ---
  async uploadFile(body) {
    if (body.file instanceof File) {
      // Direct file upload (FormData)
      const formData = new FormData();
      formData.append('file', body.file);

      // Add other fields as JSON body
      if (body.filename) formData.append('filename', body.filename);
      if (body.title) formData.append('title', body.title);
      if (body.issuing_authority) formData.append('issuing_authority', body.issuing_authority);
      if (body.document_type) formData.append('document_type', body.document_type);
      if (body.vault_id) formData.append('vault_id', body.vault_id);
      if (body.organization_id) formData.append('organization_id', body.organization_id);
      if (body.document_number) formData.append('document_number', body.document_number);
      if (body.short_title) formData.append('short_title', body.short_title);
      if (body.description) formData.append('description', body.description);
      if (body.tags !== undefined) formData.append('tags', JSON.stringify(body.tags));
      if (body.issue_date) formData.append('issue_date', body.issue_date);
      if (body.effective_date) formData.append('effective_date', body.effective_date);
      if (body.language) formData.append('language', body.language);
      if (body.visibility) formData.append('visibility', body.visibility);

      const headers = {};
      if (this.token) headers['Authorization'] = `Bearer ${this.token}`;

      const opts = { method: 'POST', headers };
      opts.body = formData;

      try {
        const resp = await fetch((API_BASE + '/v1/uploads').replace('//', '/'), opts);
        return await resp.json();
      } catch (err) {
        return {
          success: false,
          status: 0,
          error: { code: 'NETWORK_ERROR', message: `Network error: ${err.message}`, category: 'INTERNAL' },
          request_id: 'error',
          timestamp: new Date().toISOString()
        };
      }
    } else {
      // Base64 encoded upload (legacy)
      return this.request('POST', '/v1/uploads', body);
    }
  }
  async getUploadStatus(jobId) { return this.get(`/v1/uploads/${jobId}`); }

  // --- Search ---
  async search(body) { return this.post('/v1/search', body); }
  async searchSemantic(body) { return this.post('/v1/search/semantic', body); }
  async searchKeyword(body) { return this.post('/v1/search/keyword', body); }
  async searchHybrid(body) { return this.post('/v1/search/hybrid', body); }

  // --- Answers ---
  async ask(body) { return this.post('/v1/answers', body); }

  // --- Admin ---
  async listJobs(params = {}) { return this.get('/v1/jobs', params); }
  async getSystemInfo() { return this.get('/v1/system'); }
  async reindex(body = {}) { return this.post('/v1/reindex', body); }
  async reembed(body = {}) { return this.post('/v1/reembed', body); }
  async reparse(body = {}) { return this.post('/v1/reparse', body); }
  async reocr(body = {}) { return this.post('/v1/reocr', body); }

  // --- Setup (Task 026) ---
  async setupStatus() { return this.get('/v1/setup/status'); }
  async getSetupConfig() { return this.get('/v1/setup/config'); }
  async saveSetupConfig(body) { return this.post('/v1/setup/config', body); }
  async testProvider(body) { return this.post('/v1/setup/test', body); }
  async completeSetup() { return this.post('/v1/setup/complete'); }
}

const api = new ApiClient();
