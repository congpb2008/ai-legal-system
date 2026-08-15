/* Banking Legal Platform — Web UI application
   All operations go through the Platform API (api.js).
   The UI contains NO business logic — it only renders API responses. */

const app = {
  state: {
    user: null,
    currentPage: 'home',
    vaults: [],
    documents: [],
    searchResults: null,
    answer: null,
    jobs: [],
    systemInfo: null,
    documentToDelete: null,
    folderFiles: [],
  },

  // ------------------------------------------------------------------
  // Initialization
  // ------------------------------------------------------------------

  async init() {
    this.auth = new AuthModule();
    this.router = new Router();
    window.addEventListener('hashchange', () => this.router.handleRoute());

    // Sidebar toggle for mobile
    this._initSidebar();

    // Check if already authenticated
    if (api.token) {
      const resp = await api.me();
      if (resp.success) {
        this.state.user = resp.data;
        this.auth.onLogin(resp.data, false);
      } else {
        api.setToken(null);
      }
    }

    // Check first-run status — show setup wizard if not configured
    if (!this.state.user) {
      try {
        const setupResp = await api.setupStatus();
        if (setupResp.success && setupResp.data.first_run) {
          document.getElementById('loginModal').style.display = 'none';
          this.showPage('setup');
          this.renderSetup();
          return;
        }
      } catch(e) { /* ignore — show normal UI */ }
    }

    // Show login modal if not authenticated
    if (!this.state.user) {
      document.getElementById('loginModal').style.display = 'flex';
    }

    this.router.handleRoute();
  },

  _initSidebar() {
    const toggle = document.getElementById('sidebarToggle');
    const overlay = document.getElementById('sidebarOverlay');
    const sidebar = document.getElementById('sidebar');
    if (!toggle || !overlay || !sidebar) return;
    toggle.addEventListener('click', () => {
      const isOpen = sidebar.classList.toggle('open');
      overlay.classList.toggle('open');
      toggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
    });
    overlay.addEventListener('click', () => {
      sidebar.classList.remove('open');
      overlay.classList.remove('open');
    });
    // Close sidebar on nav click (mobile)
    document.querySelectorAll('.nav-item').forEach(item => {
      item.addEventListener('click', () => {
        if (window.innerWidth <= 768) {
          sidebar.classList.remove('open');
          overlay.classList.remove('open');
        }
      });
    });
  },

  // ------------------------------------------------------------------
  // Setup Wizard (Task 026)
  // ------------------------------------------------------------------

  async renderSetup() {
    const el = document.getElementById('page-setup');
    el.innerHTML = `
      <div class="card" style="max-width:600px;margin:40px auto">
        <h1>⚖️ Chào mừng đến với Legal Platform</h1>
        <p class="muted">Vui lòng cấu hình dịch vụ AI trước khi sử dụng.</p>

        <form id="setupForm" onsubmit="return app.handleSetupSubmit(event)">
          <div class="form-group">
            <label for="setupMode">Chiến lược AI</label>
            <select id="setupMode" class="form-select" onchange="app.onSetupModeChange()">
              <option value="cloud">☁️ Cloud — Sử dụng dịch vụ AI từ xa</option>
              <option value="local">💻 Local — Ollama/OpenAI-compatible trên máy này</option>
            </select>
          </div>

          <div id="cloudSettings">
            <div class="form-group">
              <label for="setupBaseUrl">Base URL <span aria-label="Bắt buộc">*</span></label>
              <input type="url" id="setupBaseUrl" class="form-input"
                     value="http://localhost:11434/v1"
                     placeholder="http://localhost:11434/v1" required aria-required="true">
              <div class="form-hint">Ví dụ: https://api.openai.com/v1 hoặc http://localhost:11434/v1</div>
            </div>
            <div class="form-group">
              <label for="setupApiKey">API Key</label>
              <input type="password" id="setupApiKey" class="form-input"
                     placeholder="sk-... (để trống nếu không cần)">
              <div class="form-hint">API key của provider. Lưu trữ an toàn, không bao giờ hiển thị.</div>
            </div>
            <div class="form-group">
              <label for="setupModel">Model <span aria-label="Bắt buộc">*</span></label>
              <input type="text" id="setupModel" class="form-input"
                     value="llama3" placeholder="llama3, gpt-4, etc." required aria-required="true">
            </div>
            <div class="form-group">
              <label for="setupTimeout">Timeout (giây)</label>
              <input type="number" id="setupTimeout" class="form-input" value="60" min="5" max="300">
            </div>
            <div class="form-group">
              <label for="setupMaxTokens">Ngân sách token trả lời</label>
              <input type="number" id="setupMaxTokens" class="form-input" value="4096" min="256" max="16384" step="256">
              <div class="form-hint">Model suy luận có thể cần 4096 token để tạo phần trả lời nhìn thấy được.</div>
            </div>
            <div class="form-group">
              <label for="setupReasoningEffort">Mức suy luận</label>
              <select id="setupReasoningEffort" class="form-select">
                <option value="">Tự động theo provider</option>
                <option value="none">Tắt — phù hợp hỏi đáp dựa trên bằng chứng</option>
                <option value="low">Thấp</option>
                <option value="medium">Trung bình</option>
                <option value="high">Cao</option>
              </select>
              <div class="form-hint">Dùng “Tắt” cho Ollama/Qwen nếu model chỉ suy luận mà không trả văn bản trong giới hạn token.</div>
            </div>
            <div class="flex gap-8">
              <button type="button" class="btn btn-outline" id="testBtn" onclick="app.runSetupTest()">🔌 Kiểm tra kết nối</button>
              <div id="testResult" class="text-sm" style="align-self:center"></div>
            </div>
          </div>

          <div class="form-error" id="setupError" style="display:none" role="alert"></div>
          <div class="modal-actions mt-16">
            <button type="submit" class="btn btn-primary" id="setupSubmitBtn">✅ Hoàn tất cài đặt</button>
          </div>
        </form>
      </div>
    `;

    try {
      const response = await api.getSetupConfig();
      if (response.success && response.data) {
        const config = response.data;
        if (config.base_url) document.getElementById('setupBaseUrl').value = config.base_url;
        if (config.model) document.getElementById('setupModel').value = config.model;
        if (config.timeout_seconds) document.getElementById('setupTimeout').value = config.timeout_seconds;
        if (config.max_tokens) document.getElementById('setupMaxTokens').value = config.max_tokens;
        document.getElementById('setupReasoningEffort').value = config.reasoning_effort || '';
        if (config.has_api_key) {
          document.getElementById('setupApiKey').placeholder = 'Đã lưu an toàn — để trống để giữ nguyên';
        }
        document.getElementById('setupMode').value = config.base_url?.includes('localhost')
          ? 'local'
          : 'cloud';
      }
    } catch (error) {
      // Defaults remain usable if a first-run config has never been saved.
    }
  },

  onSetupModeChange() {
    const mode = document.getElementById('setupMode').value;
    document.getElementById('cloudSettings').style.display = 'block';
    if (mode === 'local') {
      document.getElementById('setupBaseUrl').value = 'http://localhost:11434/v1';
    }
  },

  // ------------------------------------------------------------------
  // Delete confirmation
  // ------------------------------------------------------------------

  confirmDelete(docId) {
    this.state.documentToDelete = docId;
    document.getElementById('deleteModal').style.display = 'flex';
  },

  cancelDelete() {
    this.state.documentToDelete = null;
    document.getElementById('deleteModal').style.display = 'none';
  },

  async executeDelete() {
    const docId = this.state.documentToDelete;
    if (!docId) return;

    const errorEl = document.getElementById('deleteModalError');
    const btn = document.getElementById('confirmDeleteBtn');
    btn.disabled = true;

    try {
      const resp = await api.deleteDocument(docId);
      if (resp.success) {
        this.showToast('Tài liệu đã được lưu trữ; bản gốc vẫn được giữ lại.', 'success');
        await this.renderDocuments(); // Refresh the list
      } else {
        errorEl.textContent = resp.error?.message || 'Không thể lưu trữ tài liệu';
        errorEl.style.display = 'block';
      }
    } catch (err) {
      errorEl.textContent = `Lỗi: ${err.message}`;
      errorEl.style.display = 'block';
    } finally {
      this.state.documentToDelete = null;
      document.getElementById('deleteModal').style.display = 'none';
      btn.disabled = false;
    }
  },

  // ------------------------------------------------------------------
  // Folder upload
  // ------------------------------------------------------------------

  showFolderUpload() {
    this.state.folderFiles = [];
    document.getElementById('folderUploadModal').style.display = 'flex';
    document.getElementById('folderInput').value = '';
    document.getElementById('multiFileInput').value = '';
    document.getElementById('folderUploadError').style.display = 'none';
    document.getElementById('folderUploadStatus').innerHTML = '';
    document.getElementById('folderFilePreview').innerHTML = '';
  },

  cancelFolderUpload() {
    document.getElementById('folderUploadModal').style.display = 'none';
  },

  async handleFolderInputChange(event) {
    const files = Array.from(event.target.files);
    this.state.folderFiles = files;
    const preview = document.getElementById('folderFilePreview');
    const supported = files
      .map((file, index) => ({ file, index }))
      .filter(({ file }) => !file.name.startsWith('~$') && /\.(pdf|docx)$/i.test(file.name));
    const skipped = files.length - supported.length;
    preview.innerHTML = supported.length ? `
      <h3>Thông tin từng tài liệu</h3>
      <p class="text-sm muted">Kiểm tra tiêu đề, nhãn và mô tả trước khi tải lên.${skipped ? ` Sẽ bỏ qua ${skipped} tệp tạm/không hỗ trợ.` : ''}</p>
      ${supported.map(({ file, index }) => {
        const title = file.name.replace(/\.[^/.]+$/, '').replace(/^\d+\.\s*/, '').replace(/[_]+/g, ' ').trim();
        return `
        <fieldset class="folder-file-card" data-file-index="${index}">
          <legend>${this.esc(file.name)}</legend>
          <div class="form-group">
            <label for="folderTitle${index}">Tiêu đề hiển thị</label>
            <input id="folderTitle${index}" data-field="title" class="form-input" value="${this.esc(title)}" required>
          </div>
          <div class="form-group">
            <label for="folderNumber${index}">Số hiệu / mã</label>
            <input id="folderNumber${index}" data-field="document_number" class="form-input">
          </div>
          <div class="form-group">
            <label for="folderTags${index}">Nhãn / thẻ</label>
            <input id="folderTags${index}" data-field="tags" class="form-input" placeholder="Biểu mẫu, E-HSMT, Hàng hóa" required>
          </div>
          <div class="form-group">
            <label for="folderDescription${index}">Mô tả ngắn</label>
            <textarea id="folderDescription${index}" data-field="description" class="form-textarea" required></textarea>
          </div>
        </fieldset>`;
      }).join('')}
    ` : '<p class="text-sm muted">Không có PDF hoặc DOCX hợp lệ trong lựa chọn.</p>';
  },

  async processFolderUpload() {
    const selectedFiles = this.state.folderFiles;
    const skippedFiles = selectedFiles.filter(file => file.name.startsWith('~$'));
    const unsupportedFiles = selectedFiles.filter(file => {
      const name = file.name.toLowerCase();
      return !file.name.startsWith('~$') && !name.endsWith('.pdf') && !name.endsWith('.docx');
    });
    const files = selectedFiles.filter(file => {
      const name = file.name.toLowerCase();
      return !file.name.startsWith('~$') && (name.endsWith('.pdf') || name.endsWith('.docx'));
    });
    if (files.length === 0) {
      alert(skippedFiles.length
        ? 'Thư mục chỉ chứa tệp khóa tạm của Microsoft Office (~$); không có tài liệu để tải lên.'
        : 'Vui lòng chọn ít nhất một tệp tin');
      return;
    }

    const vaultId = document.getElementById('folderVault')?.value || '';
    const authority = document.getElementById('folderAuthority')?.value.trim() || '';
    const documentType = document.getElementById('folderType')?.value || 'INTERNAL_REGULATION';
    const issueDate = document.getElementById('folderIssueDate')?.value || '';
    if (!vaultId || !authority) {
      const errorEl = document.getElementById('folderUploadError');
      errorEl.textContent = !vaultId
        ? 'Vui lòng chọn kho tài liệu.'
        : 'Vui lòng nhập cơ quan ban hành cho thư mục.';
      errorEl.style.display = 'block';
      return;
    }

    const errorEl = document.getElementById('folderUploadError');
    const btn = document.getElementById('startFolderUploadBtn');
    const statusEl = document.getElementById('folderUploadStatus');
    btn.disabled = true;
    errorEl.style.display = 'none';
    statusEl.innerHTML = '<div class="loading">Đang xử lý...</div>';

    const results = [];
    let successCount = 0;
    let failureCount = 0;

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const fileIndex = selectedFiles.indexOf(file);
      const card = document.querySelector(`.folder-file-card[data-file-index="${fileIndex}"]`);
      const title = card?.querySelector('[data-field="title"]')?.value.trim() || '';
      const documentNumber = card?.querySelector('[data-field="document_number"]')?.value.trim() || '';
      const tags = this.parseTags(card?.querySelector('[data-field="tags"]')?.value || '');
      const description = card?.querySelector('[data-field="description"]')?.value.trim() || '';
      if (!title || tags.length === 0 || !description) {
        errorEl.textContent = `Vui lòng hoàn thành tiêu đề, nhãn và mô tả cho ${file.name}.`;
        errorEl.style.display = 'block';
        btn.disabled = false;
        return;
      }
      statusEl.innerHTML = `<div class="loading">Đang tải lên: ${i + 1} / ${files.length} - ${file.name}</div>`;

      try {
        const result = await this.uploadSingleFile(file, {
          vault_id: vaultId,
          issuing_authority: authority,
          document_type: documentType,
          title,
          document_number: documentNumber,
          tags,
          description,
          issue_date: issueDate,
        });
        if (result.success) {
          successCount++;
          results.push({ filename: file.name, status: 'success', document_id: result.data.document_id });
        } else {
          failureCount++;
          results.push({ filename: file.name, status: 'failure', error: result.error?.message });
        }
      } catch (err) {
        failureCount++;
        results.push({ filename: file.name, status: 'failure', error: err.message });
      }
    }

    statusEl.innerHTML = `
      <div class="mt-16">
        <h3>Tổng kết</h3>
        <ul>
          <li class="text-success">✅ Thành công: ${successCount}/${files.length}</li>
          <li class="text-danger">❌ Thất bại: ${failureCount}/${files.length}</li>
          ${skippedFiles.length ? `<li class="muted">⏭️ Bỏ qua tệp khóa Office (~$): ${skippedFiles.length}</li>` : ''}
          ${unsupportedFiles.length ? `<li class="muted">⏭️ Bỏ qua định dạng không hỗ trợ: ${unsupportedFiles.length}</li>` : ''}
        </ul>
        ${results.filter(r => r.status === 'failure').length > 0 ? `
          <details>
            <summary>Xem chi tiết thất bại</summary>
            <ul>
              ${results.filter(r => r.status === 'failure').map(r => `
                <li class="text-danger text-sm">${this.esc(r.filename)}: ${this.esc(r.error)}</li>
              `).join('')}
            </ul>
          </details>
        ` : ''}
      </div>
    `;

    btn.disabled = false;
  },

  async uploadSingleFile(file, metadata = {}) {
    const title = metadata.title || file.name
      .replace(/\.[^/.]+$/, '')
      .replace(/^\d+\.\s*/, '')
      .replace(/[_]+/g, ' ')
      .trim();
    const vaultEl = document.getElementById('uploadVault');
    const vaultId = metadata.vault_id || (vaultEl ? vaultEl.value : '');

    // Ensure a vault is selected — get first available if none selected
    let resolvedVaultId = vaultId;
    if (!resolvedVaultId) {
      try {
        const vaultsResp = await api.listVaults();
        if (vaultsResp.success && vaultsResp.data?.items?.length > 0) {
          // Auto-select first vault as fallback
          resolvedVaultId = vaultsResp.data.items[0].id;
        } else {
          return { success: false, status: 400, error: { code: 'NO_VAULT', message: 'No vault available. Please create a vault in the Vault tab first.' }};
        }
      } catch {
        return { success: false, status: 500, error: { code: 'VAULT_ERROR', message: 'Cannot list vaults. Check connection.' }};
      }
    }

    const result = await api.uploadFile({
      filename: file.name,
      title: title,
      issuing_authority: metadata.issuing_authority || '',
      document_type: metadata.document_type || 'INTERNAL_REGULATION',
      vault_id: resolvedVaultId,
      organization_id: '',  // Will be auto-assigned by the backend
      document_number: metadata.document_number || undefined,
      description: metadata.description || undefined,
      tags: metadata.tags || [],
      issue_date: metadata.issue_date || undefined,
      file: file,
    });
    return result;
  },

  async runSetupTest() {
    const btn = document.getElementById('testBtn');
    const resultEl = document.getElementById('testResult');
    btn.disabled = true;
    resultEl.textContent = 'Đang kiểm tra...';

    const body = {
      base_url: document.getElementById('setupBaseUrl').value.trim(),
      api_key: document.getElementById('setupApiKey').value.trim(),
      model: document.getElementById('setupModel').value.trim(),
      timeout_seconds: parseInt(document.getElementById('setupTimeout').value) || 60,
      max_tokens: parseInt(document.getElementById('setupMaxTokens').value) || 4096,
      reasoning_effort: document.getElementById('setupReasoningEffort').value,
    };

    try {
      const resp = await api.testProvider(body);
      if (resp.success && resp.data.reachable) {
        resultEl.innerHTML = '<span class="badge badge-success">✅ Kết nối thành công</span>';
      } else {
        resultEl.innerHTML = `<span class="badge badge-danger">❌ ${this.esc(resp.data?.message || 'Kết nối thất bại')}</span>`;
      }
    } catch (err) {
      resultEl.innerHTML = `<span class="badge badge-danger">❌ Lỗi: ${this.esc(err.message)}</span>`;
    } finally {
      btn.disabled = false;
    }
  },

  async handleSetupSubmit(event) {
    event.preventDefault();
    const btn = document.getElementById('setupSubmitBtn');
    const errorEl = document.getElementById('setupError');
    const mode = document.getElementById('setupMode').value;

    btn.disabled = true;
    btn.textContent = 'Đang lưu...';
    errorEl.style.display = 'none';

    try {
      if (mode === 'cloud' || mode === 'local') {
        const baseUrl = document.getElementById('setupBaseUrl').value.trim();
        const model = document.getElementById('setupModel').value.trim();

        if (!baseUrl) {
          errorEl.textContent = 'Vui lòng nhập Base URL.';
          errorEl.style.display = 'block';
          btn.disabled = false;
          btn.textContent = '✅ Hoàn tất cài đặt';
          return;
        }
        if (!model) {
          errorEl.textContent = 'Vui lòng nhập tên model.';
          errorEl.style.display = 'block';
          btn.disabled = false;
          btn.textContent = '✅ Hoàn tất cài đặt';
          return;
        }

        const configResp = await api.saveSetupConfig({
          provider_type: 'openai_compatible',
          base_url: baseUrl,
          api_key: document.getElementById('setupApiKey').value.trim(),
          model: model,
          timeout_seconds: parseInt(document.getElementById('setupTimeout').value) || 60,
          max_tokens: parseInt(document.getElementById('setupMaxTokens').value) || 4096,
          reasoning_effort: document.getElementById('setupReasoningEffort').value,
        });
        if (!configResp.success) {
          errorEl.textContent = configResp.error?.message || 'Lỗi lưu cấu hình.';
          errorEl.style.display = 'block';
          btn.disabled = false;
          btn.textContent = '✅ Hoàn tất cài đặt';
          return;
        }
      }

      // Mark setup complete
      const completeResp = await api.completeSetup();
      if (completeResp.success) {
        app.showToast('Cài đặt hoàn tất! Vui lòng đăng nhập để bắt đầu.', 'success');
        document.getElementById('loginModal').style.display = 'flex';
      } else {
        errorEl.textContent = completeResp.error?.message || 'Lỗi hoàn tất cài đặt.';
        errorEl.style.display = 'block';
      }
    } catch (err) {
      errorEl.textContent = `Lỗi: ${err.message}`;
      errorEl.style.display = 'block';
    } finally {
      btn.disabled = false;
      btn.textContent = '✅ Hoàn tất cài đặt';
    }
  },

  // ------------------------------------------------------------------
  // Page rendering
  // ------------------------------------------------------------------

  showPage(pageId) {
    document.querySelectorAll('.page').forEach(p => p.style.display = 'none');
    const page = document.getElementById(`page-${pageId}`);
    if (page) page.style.display = 'block';
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    const navItem = document.querySelector(`.nav-item[data-page="${pageId}"]`);
    if (navItem) navItem.classList.add('active');
    this.state.currentPage = pageId;
  },

  async renderHome() {
    const el = document.getElementById('page-home');
    el.innerHTML = '<div class="loading">Đang tải...</div>';
    const resp = await api.health();
    const health = resp.success ? resp.data : { status: 'unknown' };

    let vaultHtml = '<div class="empty-state"><h3>Chưa có kho tài liệu</h3><p class="text-sm">Tạo kho tài liệu đầu tiên để bắt đầu.</p></div>';
    try {
      const vResp = await api.listVaults({ limit: 5 });
      if (vResp.success) {
        const vaults = vResp.data.items || [];
        if (vaults.length > 0) {
          vaultHtml = vaults.map(v => `
            <div class="card" style="cursor:pointer" onclick="app.router.navigate('vaults')" role="button" tabindex="0" aria-label="Xem kho ${this.esc(v.name)}">
              <div class="flex-between">
                <strong>${this.esc(v.name)}</strong>
                <span class="badge badge-info">${v.vault_type}</span>
              </div>
              <div class="muted text-sm mt-8">${v.document_count || 0} tài liệu · ${v.member_count || 0} thành viên</div>
            </div>
          `).join('');
        }
      }
    } catch(e) { /* ignore */ }

    el.innerHTML = `
      <h1>Trang chủ</h1>
      <div class="card-grid">
        <div class="card">
          <h3>📤 Tải lên nhanh</h3>
          <p class="muted text-sm">Tải lên tài liệu pháp lý mới</p>
          <button class="btn btn-primary mt-8" onclick="app.router.navigate('upload')">Tải lên</button>
        </div>
        <div class="card">
          <h3>🔍 Tra cứu</h3>
          <p class="muted text-sm">Tìm kiếm trong kho tài liệu</p>
          <button class="btn btn-outline mt-8" onclick="app.router.navigate('search')">Tra cứu</button>
        </div>
        <div class="card">
          <h3>❓ Hỏi đáp</h3>
          <p class="muted text-sm">Đặt câu hỏi về tài liệu pháp lý</p>
          <button class="btn btn-outline mt-8" onclick="app.router.navigate('ask')">Hỏi</button>
        </div>
        <div class="card">
          <h3>⚙️ Hệ thống</h3>
          <p class="muted text-sm">Trạng thái: <strong>${health.status}</strong></p>
          <p class="text-sm muted">Phiên bản: ${health.version || '0.1.0'}</p>
        </div>
      </div>
      <h2 class="mt-16">Kho tài liệu</h2>
      <div class="card-grid">${vaultHtml}</div>
    `;
  },

  async renderSearch() {
    const el = document.getElementById('page-search');
    el.innerHTML = `
      <h1>Tra cứu</h1>
      <div class="card">
        <form id="searchForm" onsubmit="return app.runSearch(event)">
          <div class="flex gap-8 flex-wrap">
            <select id="searchMode" class="form-select" style="width:auto;min-width:120px" aria-label="Chế độ tìm kiếm">
              <option value="hybrid">Hybrid</option>
              <option value="semantic">Semantic</option>
              <option value="keyword">Keyword</option>
            </select>
            <input type="text" id="searchQuery" class="form-input" style="flex:1;min-width:200px"
                   placeholder="Nhập từ khóa tra cứu..." required aria-label="Từ khóa tìm kiếm">
            <button type="submit" class="btn btn-primary" id="searchBtn">Tìm kiếm</button>
          </div>
        </form>
      </div>
      <div id="searchResults"></div>
    `;
    document.getElementById('searchQuery').focus();
  },

  async runSearch(event) {
    if (event) event.preventDefault();
    const query = document.getElementById('searchQuery').value.trim();
    if (!query) return;
    const mode = document.getElementById('searchMode').value;
    const btn = document.getElementById('searchBtn');
    const resultsEl = document.getElementById('searchResults');
    btn.disabled = true;
    btn.textContent = 'Đang tìm...';
    resultsEl.innerHTML = '<div class="loading">Đang tìm kiếm...</div>';

    const body = { query, top_k: 20 };
    let resp;
    try {
      if (mode === 'semantic') resp = await api.searchSemantic(body);
      else if (mode === 'keyword') resp = await api.searchKeyword(body);
      else resp = await api.searchHybrid(body);
    } catch (err) {
      resultsEl.innerHTML = `<div class="card"><div class="form-error">Lỗi kết nối: ${this.esc(err.message)}</div></div>`;
      btn.disabled = false;
      btn.textContent = 'Tìm kiếm';
      return;
    }

    btn.disabled = false;
    btn.textContent = 'Tìm kiếm';

    if (!resp.success) {
      resultsEl.innerHTML = `<div class="card"><div class="form-error">${this.esc(resp.error?.message || 'Lỗi tìm kiếm')}</div></div>`;
      return;
    }

    const evidence = resp.data.evidence || [];
    if (evidence.length === 0) {
      resultsEl.innerHTML = '<div class="empty-state"><h3>Không tìm thấy kết quả</h3><p class="text-sm">Thử thay đổi từ khóa hoặc chế độ tìm kiếm.</p></div>';
      return;
    }

    resultsEl.innerHTML = `
      <div class="flex-between mb-16 flex-wrap">
        <span class="muted">${evidence.length} kết quả</span>
        <span class="badge badge-info">${resp.data.strategy || mode}</span>
      </div>
      ${evidence.map((e, i) => {
        const ref = e.source_anchor
          ? (typeof e.source_anchor === 'string' ? e.source_anchor : e.source_anchor.canonical_reference || '')
          : '';
        const refDisplay = ref || `Kết quả #${i + 1}`;
        const sourceTargetId = `citation-source-search-${e.id}`;
        return `
        <div class="card result-card">
          <div class="result-title">${this.esc(e.document_title || refDisplay)}</div>
          ${(e.document_tags || []).length ? `<div class="mt-8">${e.document_tags.map(tag => `<span class="badge badge-neutral mr-4">${this.esc(tag)}</span>`).join('')}</div>` : ''}
          ${ref ? `<div class="result-ref">${this.esc(ref)}</div>` : ''}
          <div class="result-preview">${this.highlight(this.esc(e.text || ''), query)}</div>
          <div class="result-actions">
            <span class="badge ${e.score >= 0.8 ? 'badge-success' : e.score >= 0.5 ? 'badge-warning' : 'badge-neutral'}">
              ${(e.score * 100).toFixed(0)}%
            </span>
            <button class="btn btn-sm btn-outline" onclick="app.copyCitation('${this.esc(ref)}')" ${ref ? '' : 'disabled'}>
              📋 Sao chép
            </button>
            ${e.document_id && e.knowledge_node_id ? `
            <button class="btn btn-sm btn-outline"
              onclick="app.showCitationSource('${e.document_id}', '${e.knowledge_node_id}', '${e.source_anchor?.page || ''}', 'search-${e.id}')">
              Xem nguồn
            </button>` : ''}
          </div>
          <div id="${sourceTargetId}" class="mt-8"></div>
        </div>`;
      }).join('')}
    `;
  },

  async renderAsk() {
    const el = document.getElementById('page-ask');
    el.innerHTML = `
      <h1>Hỏi đáp</h1>
      <div class="card">
        <form id="askForm" onsubmit="return app.runAsk(event)">
          <div class="form-group">
            <label for="askQuery">Câu hỏi của bạn</label>
            <textarea id="askQuery" class="form-textarea" placeholder="Nhập câu hỏi về tài liệu pháp lý..."
                      style="min-height:80px" required aria-label="Câu hỏi"></textarea>
            <div class="form-hint">Nhấn Ctrl+Enter để gửi nhanh</div>
          </div>
          <button type="submit" class="btn btn-primary" id="askBtn">Gửi câu hỏi</button>
        </form>
      </div>
      <div id="askResults"></div>
    `;
    const ta = document.getElementById('askQuery');
    ta.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && e.ctrlKey) app.runAsk(e);
    });
    ta.focus();
  },

  async runAsk(event) {
    if (event) event.preventDefault();
    const query = document.getElementById('askQuery').value.trim();
    if (!query) return;
    const btn = document.getElementById('askBtn');
    const resultsEl = document.getElementById('askResults');
    btn.disabled = true;
    btn.textContent = 'Đang xử lý...';
    resultsEl.innerHTML = '<div class="loading">Đang xử lý câu hỏi...</div>';

    let resp;
    try {
      resp = await api.ask({ query });
    } catch (err) {
      resultsEl.innerHTML = `<div class="card"><div class="form-error">Lỗi kết nối: ${this.esc(err.message)}</div></div>`;
      btn.disabled = false;
      btn.textContent = 'Gửi câu hỏi';
      return;
    }

    btn.disabled = false;
    btn.textContent = 'Gửi câu hỏi';

    if (!resp.success) {
      resultsEl.innerHTML = `<div class="card"><div class="form-error">${this.esc(resp.error?.message || 'Lỗi xử lý')}</div></div>`;
      return;
    }

    const a = resp.data;
    const confLevel = a.confidence?.level || 'MEDIUM';
    const confScore = a.confidence?.score || 0;
    const confColor = confLevel === 'HIGH' ? 'badge-success' : confLevel === 'MEDIUM' ? 'badge-warning' : 'badge-danger';

    resultsEl.innerHTML = `
      <div class="card">
        <div class="flex-between mb-16 flex-wrap">
          <div class="flex gap-8 flex-wrap">
            <span class="badge ${a.status === 'SUCCESS' ? 'badge-success' : a.status === 'PARTIAL' ? 'badge-warning' : 'badge-danger'}">
              ${a.status}
            </span>
            <span class="badge ${confColor}">${confLevel} (${(confScore * 100).toFixed(0)}%)</span>
          </div>
        </div>

        <div class="answer-content">${this.renderMarkdown(a.response?.content || '')}</div>

        ${a.citations?.length > 0 ? `
          <h3>Trích dẫn (${a.citations.length})</h3>
          <div class="confidence-bar mt-8" role="progressbar" aria-valuenow="${Math.round(confScore * 100)}" aria-valuemin="0" aria-valuemax="100">
            <div class="confidence-fill" style="width:${confScore * 100}%"></div>
          </div>
          <ul class="citation-list mt-8">
            ${a.citations.map(c => {
              const anchor = c.source_anchor || {};
              const pageLabel = anchor.page ? ` · Trang ${anchor.page}` : '';
              return `
              <li class="citation-item">
                <details>
                  <summary>${this.esc(c.document_title || 'Tài liệu')} — ${this.esc(c.label || `Trích dẫn #${(c.id || '').slice(0, 8)}`)}${this.esc(pageLabel)}</summary>
                  <div class="citation-detail">
                    <div><strong>Vị trí:</strong> ${this.esc(anchor.canonical_reference || c.label || '')}${anchor.page ? `, trang ${anchor.page}` : ''}</div>
                    ${(c.document_tags || []).length ? `<div class="mt-8">${c.document_tags.map(tag => `<span class="badge badge-neutral mr-4">${this.esc(tag)}</span>`).join('')}</div>` : ''}
                    <button type="button" class="btn btn-outline mt-8"
                      onclick="app.showCitationSource('${c.document_id}', '${c.knowledge_node_id}', '${anchor.page || ''}', '${c.id}')">
                      Xem nguồn
                    </button>
                    <div id="citation-source-${c.id}" class="mt-8"></div>
                  </div>
                </details>
              </li>
            `}).join('')}
          </ul>
        ` : ''}

        ${a.limitations?.length > 0 ? `
          <div class="mt-16">
            <h3>Lưu ý</h3>
            <ul>
              ${a.limitations.map(l => `<li class="text-sm muted">${this.esc(typeof l === 'string' ? l : l.description || '')}</li>`).join('')}
            </ul>
          </div>
        ` : ''}
      </div>
    `;
  },

  async showCitationSource(documentId, nodeId, page, citationId) {
    const target = document.getElementById(`citation-source-${citationId}`);
    if (!target) return;
    target.innerHTML = '<div class="loading">Đang kiểm tra nguồn...</div>';
    const response = await api.getDocumentSource(documentId, {
      node_id: nodeId,
      page: page || undefined,
    });
    if (!response.success) {
      target.innerHTML = `<div class="form-error">${this.esc(response.error?.message || 'Không thể mở nguồn.')}</div>`;
      return;
    }
    const source = response.data;
    const visibleText = source.node?.text || source.page?.text || '';
    target.innerHTML = `
      <div class="card" style="background:var(--surface-muted, #f7f7f8)">
        <div><strong>${this.esc(source.title)}</strong></div>
        <div class="text-sm muted">${this.esc(source.filename)}${source.page?.number ? ` · Trang ${source.page.number}` : ''}</div>
        <blockquote class="mt-8" style="white-space:pre-wrap">${this.esc(visibleText || 'Không có văn bản trích xuất cho vị trí này.')}</blockquote>
        <button type="button" class="btn btn-outline mt-8"
          onclick="app.downloadCitationSource('${documentId}', '${citationId}')">
          Tải bản gốc
        </button>
        <span id="citation-download-${citationId}" class="text-sm muted"></span>
      </div>
    `;
  },

  async downloadCitationSource(documentId, citationId) {
    const status = document.getElementById(`citation-download-${citationId}`);
    if (status) status.textContent = ' Đang chuẩn bị...';
    const response = await api.getDocumentSource(documentId, { include_original: '1' });
    if (!response.success || !response.data?.content_base64) {
      if (status) status.textContent = ` ${response.error?.message || 'Không thể tải bản gốc.'}`;
      return;
    }
    const binary = atob(response.data.content_base64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
    const blob = new Blob([bytes], { type: response.data.mime_type || 'application/octet-stream' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = response.data.filename || 'source';
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    if (status) status.textContent = ' Đã tải.';
  },

  async renderVaults() {
    const el = document.getElementById('page-vaults');
    el.innerHTML = '<div class="loading">Đang tải...</div>';

    const resp = await api.listVaults();
    if (!resp.success) {
      el.innerHTML = `<div class="empty-state"><h3>Không thể tải danh sách</h3><p class="text-sm">${this.esc(resp.error?.message || 'Vui lòng thử lại sau.')}</p></div>`;
      return;
    }

    const vaults = resp.data.items || [];
    el.innerHTML = `
      <div class="flex-between mb-16 flex-wrap">
        <h1>Kho tài liệu</h1>
        <button class="btn btn-primary" onclick="app.showCreateVaultModal()" aria-label="Tạo kho tài liệu mới">+ Tạo mới</button>
      </div>
      ${vaults.length === 0 ? '<div class="empty-state"><h3>Chưa có kho tài liệu</h3><p class="text-sm">Tạo kho tài liệu đầu tiên để bắt đầu.</p></div>' : `
      <div class="card-grid">
        ${vaults.map(v => `
          <div class="card" onclick="app.router.navigate('documents', 'vault_id=${v.id}')" style="cursor:pointer" role="button" tabindex="0" aria-label="Xem tài liệu trong kho ${this.esc(v.name)}">
            <div class="flex-between">
              <strong>${this.esc(v.name)}</strong>
              <span class="badge badge-info">${v.vault_type}</span>
            </div>
            <p class="text-sm muted mt-8">${this.esc(v.description || '')}</p>
            <div class="flex gap-8 mt-8 text-sm">
              <span>📄 ${v.document_count || 0} tài liệu</span>
              <span>👥 ${v.member_count || 0} thành viên</span>
            </div>
            <div class="flex gap-8 mt-8">
              <span class="badge ${v.status === 'ACTIVE' ? 'badge-success' : 'badge-neutral'}">${v.status}</span>
            </div>
          </div>
        `).join('')}
      </div>`}
    `;
  },

  async renderDocuments(params = {}) {
    const el = document.getElementById('page-documents');
    el.innerHTML = '<div class="loading">Đang tải...</div>';

    const resp = await api.listDocuments({ ...params, status: params.status || 'ACTIVE' });
    if (!resp.success) {
      el.innerHTML = `<div class="empty-state"><h3>Không thể tải danh sách</h3><p class="text-sm">${this.esc(resp.error?.message || 'Vui lòng thử lại sau.')}</p></div>`;
      return;
    }

    const docs = resp.data.items || [];
    this.state.documents = docs;
    const allTags = [...new Set(docs.flatMap(d => d.tags || []))].sort((a, b) => a.localeCompare(b, 'vi'));
    el.innerHTML = `
      <div class="flex-between mb-16 flex-wrap">
        <h1>Tài liệu</h1>
        <label class="text-sm" for="documentTagFilter">Lọc theo nhãn
          <select id="documentTagFilter" class="form-select" onchange="app.filterDocumentsByTag(this.value)">
            <option value="">Tất cả nhãn</option>
            ${allTags.map(tag => `<option value="${this.esc(tag)}">${this.esc(tag)}</option>`).join('')}
          </select>
        </label>
      </div>
      ${docs.length === 0 ? '<div class="empty-state"><h3>Chưa có tài liệu nào</h3><p class="text-sm">Tải lên tài liệu để bắt đầu tra cứu.</p></div>' : `
      <div class="table-responsive" role="region" tabindex="0" aria-label="Danh sách tài liệu, có thể cuộn ngang">
        <table class="table">
          <thead>
            <tr>
              <th>Tiêu đề</th>
              <th>Loại</th>
              <th>Nhãn</th>
              <th>Cơ quan ban hành</th>
              <th>Xử lý</th>
              <th>Ngày tạo</th>
              <th>Thao tác</th>
            </tr>
          </thead>
          <tbody>
            ${docs.map(d => `
              <tr data-document-tags="${this.esc((d.tags || []).join('|'))}">
                <td><strong>${this.esc(d.title)}</strong>${d.description ? `<div class="text-sm muted">${this.esc(d.description)}</div>` : ''}</td>
                <td><span class="badge badge-info">${d.type}</span></td>
                <td>${(d.tags || []).map(tag => `<span class="badge badge-neutral mr-4">${this.esc(tag)}</span>`).join('') || '—'}</td>
                <td class="muted">${this.esc(d.issuing_authority || '—')}</td>
                <td><span class="badge ${d.processing_state === 'READY' ? 'badge-success' : d.processing_state === 'FAILED' ? 'badge-danger' : 'badge-info'}">${this.esc(d.processing_state || d.status)}</span></td>
                <td class="text-sm muted">${d.created_at ? new Date(d.created_at).toLocaleDateString('vi-VN') : '—'}</td>
                <td>
                  <button class="btn btn-sm btn-outline" onclick="app.showDocumentDetail('${d.id}')" aria-label="Xem chi tiết tài liệu">Xem</button>
                  ${d.status === 'ACTIVE' ? `<button class="btn btn-sm btn-danger" onclick="app.confirmDelete('${d.id}')" aria-label="Lưu trữ tài liệu">Lưu trữ</button>` : ''}
                </td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>`}
    `;
  },

  filterDocumentsByTag(tag) {
    document.querySelectorAll('tr[data-document-tags]').forEach(row => {
      const tags = (row.dataset.documentTags || '').split('|');
      row.style.display = !tag || tags.includes(tag) ? '' : 'none';
    });
  },

  async renderUpload() {
    const el = document.getElementById('page-upload');
    el.innerHTML = `
      <div class="flex justify-between items-center gap-8 mb-16">
        <h1>Tải lên tài liệu</h1>
        <button type="button" class="btn btn-outline" onclick="app.showFolderUpload()">Tải lên thư mục</button>
      </div>
      <div class="card">
        <form id="uploadForm" onsubmit="return app.handleUpload(event)">
          <div class="form-group">
            <label for="uploadFile">Tệp tin (PDF, DOCX) <span aria-label="Bắt buộc">*</span></label>
            <input type="file" id="uploadFile" class="form-input" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" required aria-required="true">
          </div>
          <div class="form-group">
            <label for="uploadTitle">Tiêu đề <span aria-label="Bắt buộc">*</span></label>
            <input type="text" id="uploadTitle" class="form-input" placeholder="Nhập tiêu đề tài liệu" required aria-required="true">
          </div>
          <div class="form-group">
            <label for="uploadAuthority">Cơ quan ban hành <span aria-label="Bắt buộc">*</span></label>
            <input type="text" id="uploadAuthority" class="form-input" placeholder="Ví dụ: Ngân hàng Nhà nước" required aria-required="true">
          </div>
          <div class="form-group">
            <label for="uploadNumber">Số hiệu văn bản</label>
            <input type="text" id="uploadNumber" class="form-input" placeholder="Ví dụ: 90/2025/QH15">
          </div>
          <div class="form-group">
            <label for="uploadDescription">Mô tả ngắn</label>
            <textarea id="uploadDescription" class="form-textarea"
                      placeholder="Nội dung hoặc mục đích chính của tài liệu"></textarea>
          </div>
          <div class="form-group">
            <label for="uploadTags">Nhãn / thẻ <span aria-label="Bắt buộc">*</span></label>
            <input type="text" id="uploadTags" class="form-input"
                   placeholder="Ví dụ: Luật, Đấu thầu, Quốc hội" required aria-required="true">
            <div class="form-hint">Phân tách các nhãn bằng dấu phẩy.</div>
          </div>
          <div class="form-group">
            <label for="uploadIssueDate">Ngày ban hành</label>
            <input type="date" id="uploadIssueDate" class="form-input">
          </div>
          <div class="form-group">
            <label for="uploadType">Loại tài liệu</label>
            <select id="uploadType" class="form-select">
              <option value="INTERNAL_REGULATION">Nội quy</option>
              <option value="DECISION">Quyết định</option>
              <option value="CIRCULAR">Thông tư</option>
              <option value="DECREE">Nghị định</option>
              <option value="LAW">Luật</option>
              <option value="INTERNAL_POLICY">Chính sách nội bộ</option>
            </select>
          </div>
          <div class="form-group">
            <label for="uploadVault">Kho tài liệu <span aria-label="Bắt buộc">*</span></label>
            <select id="uploadVault" class="form-select" required aria-required="true">
              <option value="">Chọn kho tài liệu...</option>
            </select>
          </div>
          <div class="form-error" id="uploadError" style="display:none" role="alert"></div>
          <button type="submit" class="btn btn-primary btn-block" id="uploadBtn">Tải lên</button>
        </form>
      </div>
      <div id="uploadStatus"></div>
    `;

    // Load vaults for the dropdown
    try {
      const vResp = await api.listVaults();
      if (vResp.success) {
        const selects = [
          document.getElementById('uploadVault'),
          document.getElementById('folderVault'),
        ].filter(Boolean);
        (vResp.data.items || []).forEach(v => {
          selects.forEach(select => {
            const opt = document.createElement('option');
            opt.value = v.id;
            opt.textContent = `${v.name} (${v.vault_type})`;
            select.appendChild(opt);
          });
        });
      }
    } catch(e) { /* ignore */ }
  },

  async handleUpload(event) {
    event.preventDefault();
    const fileInput = document.getElementById('uploadFile');
    const title = document.getElementById('uploadTitle').value.trim();
    const authority = document.getElementById('uploadAuthority').value.trim();
    const documentNumber = document.getElementById('uploadNumber').value.trim();
    const description = document.getElementById('uploadDescription').value.trim();
    const tags = this.parseTags(document.getElementById('uploadTags').value);
    const issueDate = document.getElementById('uploadIssueDate').value;
    const type = document.getElementById('uploadType').value;
    const vaultId = document.getElementById('uploadVault').value;
    const errorEl = document.getElementById('uploadError');
    const btn = document.getElementById('uploadBtn');

    // Client-side validation
    if (!fileInput.files || !fileInput.files[0]) {
      errorEl.textContent = 'Vui lòng chọn tệp tin.';
      errorEl.style.display = 'block';
      return;
    }
    if (!title) {
      errorEl.textContent = 'Vui lòng nhập tiêu đề.';
      errorEl.style.display = 'block';
      return;
    }
    if (!authority) {
      errorEl.textContent = 'Vui lòng nhập cơ quan ban hành.';
      errorEl.style.display = 'block';
      return;
    }
    if (!vaultId) {
      errorEl.textContent = 'Vui lòng chọn kho tài liệu.';
      errorEl.style.display = 'block';
      return;
    }
    if (tags.length === 0) {
      errorEl.textContent = 'Vui lòng nhập ít nhất một nhãn cho tài liệu.';
      errorEl.style.display = 'block';
      return;
    }

    errorEl.style.display = 'none';
    btn.disabled = true;
    btn.textContent = 'Đang tải lên...';

    try {
      const file = fileInput.files[0];

      // Validate file size (100 MB max)
      if (file.size > 100 * 1024 * 1024) {
        errorEl.textContent = 'Tệp tin quá lớn. Kích thước tối đa là 100 MB.';
        errorEl.style.display = 'block';
        btn.disabled = false;
        btn.textContent = 'Tải lên';
        return;
      }

      // Use FormData-based upload for reliable binary transfer
      const resp = await api.uploadFile({
        file: file,
        filename: file.name,
        title: title,
        issuing_authority: authority,
        document_type: type,
        vault_id: vaultId,
        document_number: documentNumber || undefined,
        description: description || undefined,
        tags,
        issue_date: issueDate || undefined,
      });

      if (resp.success) {
        document.getElementById('uploadStatus').innerHTML = `
          <div class="card">
            <h3>✅ Tải lên thành công</h3>
            <p class="text-sm muted">Mã tài liệu: ${resp.data.document_id}</p>
            <p class="text-sm muted">Kích thước: ${(resp.data.size_bytes / 1024).toFixed(1)} KB</p>
            ${resp.data.duplicate_candidates?.length > 0 ? `
              <div class="badge badge-warning mt-8">⚠️ Phát hiện tài liệu trùng lặp</div>
            ` : ''}
            <div class="flex gap-8 mt-8">
              <button class="btn btn-outline" onclick="app.router.navigate('documents')">Xem danh sách</button>
              <button class="btn btn-outline" onclick="app.router.navigate('upload')">Tải lên tiếp</button>
            </div>
          </div>
        `;
        // Reset form
        document.getElementById('uploadForm').reset();
        app.showToast('Tải lên thành công!', 'success');
      } else {
        errorEl.textContent = resp.error?.message || 'Lỗi tải lên.';
        errorEl.style.display = 'block';
      }
    } catch (err) {
      errorEl.textContent = `Lỗi: ${err.message}`;
      errorEl.style.display = 'block';
    } finally {
      btn.disabled = false;
      btn.textContent = 'Tải lên';
    }
  },

  async renderAdmin() {
    const el = document.getElementById('page-admin');
    el.innerHTML = '<div class="loading">Đang tải...</div>';

    const [jobsResp, sysResp, docsResp] = await Promise.all([
      api.listJobs({ limit: 20 }),
      api.getSystemInfo(),
      api.listDocuments({ limit: 100 }),
    ]);

    const jobs = jobsResp.success ? (jobsResp.data.jobs || []) : [];
    const sys = sysResp.success ? sysResp.data : {};
    const docs = docsResp.success ? (docsResp.data.items || []) : [];

    el.innerHTML = `
      <h1>Quản trị hệ thống</h1>

      <div class="card-grid mb-16">
        <div class="card">
          <h3>📊 Hệ thống</h3>
          <p class="text-sm">Phiên bản: <strong>${sys.version || '0.1.0'}</strong></p>
          <p class="text-sm">Tổng số tài liệu: <strong>${sys.document_count || 0}</strong></p>
          <p class="text-sm">Mục lục: <strong>${sys.index?.total_entries || 0}</strong> bản ghi</p>
        </div>
        <div class="card">
          <h3>🔄 Tác vụ</h3>
          <label for="adminDocument" class="text-sm">Tài liệu cần xử lý</label>
          <select id="adminDocument" class="form-select mt-8">
            <option value="">Chọn một tài liệu...</option>
            ${docs.map(d => `<option value="${d.id}">${this.esc(d.title)} (${this.esc(d.processing_state || d.status)})</option>`).join('')}
          </select>
          <div class="flex gap-8 flex-wrap mt-8">
            <button class="btn btn-sm btn-outline" onclick="app.runAdminReindex()" id="reindexBtn">Re-index</button>
            <button class="btn btn-sm btn-outline" onclick="app.runAdminReembed()" id="reembedBtn">Re-embed</button>
            <button class="btn btn-sm btn-outline" onclick="app.runAdminReparse()" id="reparseBtn">Re-parse</button>
            <button class="btn btn-sm btn-outline" onclick="app.runAdminReocr()" id="reocrBtn">Re-OCR</button>
          </div>
          <div id="adminActionResult" class="mt-8 text-sm"></div>
        </div>
      </div>

      <h2>Công việc gần đây</h2>
      ${jobs.length === 0 ? '<div class="empty-state"><h3>Chưa có công việc nào</h3></div>' : `
      <div class="table-responsive" role="region" tabindex="0" aria-label="Danh sách công việc, có thể cuộn ngang">
        <table class="table">
          <thead>
            <tr>
              <th>Tài liệu</th>
              <th>Trạng thái</th>
              <th>Xử lý</th>
              <th>Kết quả</th>
              <th>Ngày tạo</th>
            </tr>
          </thead>
          <tbody>
            ${jobs.map(j => `
              <tr>
                <td>${this.esc(j.title)}</td>
                <td><span class="badge ${j.status === 'COMPLETED' ? 'badge-success' : j.status === 'FAILED' ? 'badge-danger' : 'badge-info'}">${j.status}</span></td>
                <td><span class="badge badge-info">${j.processing_state || '—'}</span></td>
                <td class="text-sm ${j.error ? 'text-danger' : 'muted'}">${this.esc(j.error || '—')}</td>
                <td class="text-sm muted">${j.created_at ? new Date(j.created_at).toLocaleDateString('vi-VN') : '—'}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>`}
    `;
  },

  async runAdminReindex() {
    const el = document.getElementById('adminActionResult');
    const btn = document.getElementById('reindexBtn');
    const body = this.adminReprocessBody();
    if (!body) return;
    btn.disabled = true;
    el.textContent = 'Đang thực hiện...';
    const resp = await api.reindex(body);
    btn.disabled = false;
    el.innerHTML = resp.success
      ? `<span class="badge badge-success">✅ Re-index hoàn tất cho ${resp.data.completed_count} tài liệu (${resp.data.completed.reduce((sum, item) => sum + item.indexed_entries, 0)} mục).</span>`
      : `<span class="badge badge-danger">❌ ${this.esc(resp.error?.message || 'Re-index thất bại')}</span>`;
  },

  async runAdminReembed() {
    const el = document.getElementById('adminActionResult');
    const btn = document.getElementById('reembedBtn');
    const body = this.adminReprocessBody();
    if (!body) return;
    btn.disabled = true;
    el.textContent = 'Đang thực hiện...';
    const resp = await api.reembed(body);
    btn.disabled = false;
    el.innerHTML = resp.success
      ? `<span class="badge badge-success">✅ Re-embed hoàn tất cho ${resp.data.completed_count} tài liệu.</span>`
      : `<span class="badge badge-danger">❌ ${this.esc(resp.error?.message || 'Re-embed thất bại')}</span>`;
  },

  async runAdminReparse() {
    const el = document.getElementById('adminActionResult');
    const btn = document.getElementById('reparseBtn');
    const body = this.adminReprocessBody();
    if (!body) return;
    btn.disabled = true;
    el.textContent = 'Đang thực hiện...';
    const resp = await api.reparse(body);
    btn.disabled = false;
    el.innerHTML = resp.success
      ? `<span class="badge badge-success">✅ Re-parse hoàn tất cho ${resp.data.completed_count} tài liệu.</span>`
      : `<span class="badge badge-danger">❌ ${this.esc(resp.error?.message || 'Re-parse thất bại')}</span>`;
  },

  async runAdminReocr() {
    const el = document.getElementById('adminActionResult');
    const btn = document.getElementById('reocrBtn');
    const body = this.adminReprocessBody();
    if (!body) return;
    btn.disabled = true;
    el.textContent = 'Đang thực hiện...';
    const resp = await api.reocr(body);
    btn.disabled = false;
    el.innerHTML = resp.success
      ? `<span class="badge badge-success">✅ Re-OCR hoàn tất cho ${resp.data.completed_count} tài liệu.</span>`
      : `<span class="badge badge-danger">❌ ${this.esc(resp.error?.message || 'Re-OCR thất bại')}</span>`;
  },

  adminReprocessBody() {
    const selected = document.getElementById('adminDocument')?.value;
    if (!selected) {
      const el = document.getElementById('adminActionResult');
      if (el) el.innerHTML = '<span class="text-danger">Vui lòng chọn một tài liệu để tránh chạy tác vụ ngoài ý muốn.</span>';
      return null;
    }
    return { document_id: selected };
  },

  // ------------------------------------------------------------------
  // Document detail panel
  // ------------------------------------------------------------------

  async showDocumentDetail(docId) {
    const resp = await api.getDocument(docId);
    if (!resp.success) {
      app.showToast('Không thể tải thông tin tài liệu.', 'error');
      return;
    }
    const d = resp.data;

    // Remove existing detail panel
    const existing = document.querySelector('.doc-detail-overlay');
    if (existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.className = 'doc-detail-overlay';
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');
    overlay.setAttribute('aria-label', 'Chi tiết tài liệu');
    overlay.innerHTML = `
      <div class="doc-detail-panel">
        <div class="flex-between">
          <h2>${this.esc(d.title)}</h2>
          <button class="btn btn-sm btn-outline" onclick="this.closest('.doc-detail-overlay').remove()" aria-label="Đóng">✕</button>
        </div>
        <div class="doc-detail-row">
          <span class="doc-detail-label">Mã tài liệu</span>
          <span class="doc-detail-value">${d.id}</span>
        </div>
        <div class="doc-detail-row">
          <span class="doc-detail-label">Loại</span>
          <span class="doc-detail-value">${d.type}</span>
        </div>
        <div class="doc-detail-row">
          <span class="doc-detail-label">Cơ quan ban hành</span>
          <span class="doc-detail-value">${this.esc(d.issuing_authority || '—')}</span>
        </div>
        <div class="doc-detail-row">
          <span class="doc-detail-label">Số hiệu</span>
          <span class="doc-detail-value">${this.esc(d.document_number || '—')}</span>
        </div>
        <div class="doc-detail-row">
          <span class="doc-detail-label">Ngôn ngữ</span>
          <span class="doc-detail-value">${d.language || 'vi'}</span>
        </div>
        <div class="doc-detail-row">
          <span class="doc-detail-label">Vòng đời</span>
          <span class="doc-detail-value"><span class="badge ${d.status === 'ACTIVE' ? 'badge-success' : 'badge-neutral'}">${d.status}</span></span>
        </div>
        <div class="doc-detail-row">
          <span class="doc-detail-label">Xử lý</span>
          <span class="doc-detail-value"><span class="badge ${d.processing_state === 'READY' ? 'badge-success' : d.processing_state === 'FAILED' ? 'badge-danger' : 'badge-info'}">${this.esc(d.processing_state || 'Chưa bắt đầu')}</span></span>
        </div>
        ${d.processing_error ? `
        <div class="doc-detail-row">
          <span class="doc-detail-label">Lỗi xử lý</span>
          <span class="doc-detail-value text-danger">${this.esc(d.processing_error)}</span>
        </div>` : ''}
        <div class="doc-detail-row">
          <span class="doc-detail-label">Kho tài liệu</span>
          <span class="doc-detail-value">${d.vault_id}</span>
        </div>
        <div class="doc-detail-row">
          <span class="doc-detail-label">Ngày tạo</span>
          <span class="doc-detail-value">${d.created_at ? new Date(d.created_at).toLocaleString('vi-VN') : '—'}</span>
        </div>
        <div class="doc-detail-row">
          <span class="doc-detail-label">Phiên bản</span>
          <span class="doc-detail-value">${d.version_count || 0}</span>
        </div>
        ${d.description ? `
        <div class="doc-detail-row">
          <span class="doc-detail-label">Mô tả</span>
          <span class="doc-detail-value">${this.esc(d.description)}</span>
        </div>` : ''}
        <div class="doc-detail-row">
          <span class="doc-detail-label">Tệp gốc</span>
          <span class="doc-detail-value">${this.esc(d.original_filename || '—')}</span>
        </div>
        <div class="doc-detail-row">
          <span class="doc-detail-label">Nhãn</span>
          <span class="doc-detail-value">${(d.tags || []).map(tag => `<span class="badge badge-neutral mr-4">${this.esc(tag)}</span>`).join('') || '—'}</span>
        </div>
        ${d.issue_date ? `
        <div class="doc-detail-row">
          <span class="doc-detail-label">Ngày ban hành</span>
          <span class="doc-detail-value">${new Date(d.issue_date).toLocaleDateString('vi-VN')}</span>
        </div>` : ''}
        <details class="mt-16">
          <summary>Chỉnh sửa tiêu đề, mô tả và nhãn</summary>
          <div class="form-group mt-8">
            <label for="editTitle">Tiêu đề</label>
            <input id="editTitle" class="form-input" value="${this.esc(d.title)}">
          </div>
          <div class="form-group">
            <label for="editDescription">Mô tả ngắn</label>
            <textarea id="editDescription" class="form-textarea">${this.esc(d.description || '')}</textarea>
          </div>
          <div class="form-group">
            <label for="editTags">Nhãn / thẻ</label>
            <input id="editTags" class="form-input" value="${this.esc((d.tags || []).join(', '))}">
          </div>
          <button type="button" class="btn btn-primary" onclick="app.saveDocumentMetadata('${d.id}')">Lưu thông tin</button>
          <span id="editDocumentResult" class="text-sm muted"></span>
        </details>
        <div id="citation-source-detail-${d.id}" class="mt-8"></div>
        <div class="modal-actions">
          <button class="btn btn-outline" onclick="app.showCitationSource('${d.id}', '', '', 'detail-${d.id}')">Mở nguồn</button>
          <button class="btn btn-outline" onclick="this.closest('.doc-detail-overlay').remove()">Đóng</button>
        </div>
      </div>
    `;

    // Close on overlay click
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) overlay.remove();
    });

    // Close on Escape
    const escHandler = (e) => {
      if (e.key === 'Escape') {
        overlay.remove();
        document.removeEventListener('keydown', escHandler);
      }
    };
    document.addEventListener('keydown', escHandler);

    document.body.appendChild(overlay);
  },

  async saveDocumentMetadata(docId) {
    const result = document.getElementById('editDocumentResult');
    const title = document.getElementById('editTitle')?.value.trim() || '';
    const description = document.getElementById('editDescription')?.value.trim() || '';
    const tags = this.parseTags(document.getElementById('editTags')?.value || '');
    if (!title || !description || tags.length === 0) {
      result.textContent = ' Cần có tiêu đề, mô tả và ít nhất một nhãn.';
      result.className = 'text-sm text-danger';
      return;
    }
    const response = await api.updateDocument(docId, { title, description, tags });
    if (!response.success) {
      result.textContent = ` ${response.error?.message || 'Không thể lưu thông tin.'}`;
      result.className = 'text-sm text-danger';
      return;
    }
    result.textContent = ' Đã lưu.';
    result.className = 'text-sm text-success';
    app.showToast('Đã cập nhật thông tin tài liệu.', 'success');
  },

  // ------------------------------------------------------------------
  // Create vault modal
  // ------------------------------------------------------------------

  showCreateVaultModal() {
    // Remove existing modal
    const existing = document.querySelector('.modal-overlay:not(#loginModal)');
    if (existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');
    overlay.setAttribute('aria-label', 'Tạo kho tài liệu mới');
    overlay.innerHTML = `
      <div class="modal">
        <div class="modal-header">
          <h2>Tạo kho tài liệu mới</h2>
        </div>
        <form id="createVaultForm" onsubmit="return app.handleCreateVault(event)">
          <div class="form-group">
            <label for="vaultName">Tên kho tài liệu <span aria-label="Bắt buộc">*</span></label>
            <input type="text" id="vaultName" class="form-input" placeholder="Nhập tên kho tài liệu" required aria-required="true">
          </div>
          <div class="form-group">
            <label for="vaultType">Loại kho</label>
            <select id="vaultType" class="form-select">
              <option value="DEPARTMENT">Department</option>
              <option value="COMMON">Common</option>
              <option value="PROJECT">Project</option>
              <option value="PERSONAL">Personal</option>
            </select>
          </div>
          <div class="form-group">
            <label for="vaultDesc">Mô tả (không bắt buộc)</label>
            <input type="text" id="vaultDesc" class="form-input" placeholder="Mô tả ngắn về kho tài liệu">
          </div>
          <div class="form-error" id="vaultError" style="display:none" role="alert"></div>
          <div class="modal-actions">
            <button type="button" class="btn btn-outline" onclick="this.closest('.modal-overlay').remove()">Hủy</button>
            <button type="submit" class="btn btn-primary" id="createVaultBtn">Tạo</button>
          </div>
        </form>
      </div>
    `;

    // Close on overlay click
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) overlay.remove();
    });

    document.body.appendChild(overlay);
    document.getElementById('vaultName').focus();
  },

  async handleCreateVault(event) {
    event.preventDefault();
    const name = document.getElementById('vaultName').value.trim();
    const type = document.getElementById('vaultType').value;
    const desc = document.getElementById('vaultDesc').value.trim();
    const errorEl = document.getElementById('vaultError');
    const btn = document.getElementById('createVaultBtn');

    if (!name) {
      errorEl.textContent = 'Vui lòng nhập tên kho tài liệu.';
      errorEl.style.display = 'block';
      return;
    }

    errorEl.style.display = 'none';
    btn.disabled = true;
    btn.textContent = 'Đang tạo...';

    try {
      const resp = await api.createVault({ name, vault_type: type, description: desc || undefined });
      if (resp.success) {
        const overlay = btn.closest('.modal-overlay');
        if (overlay) overlay.remove();
        app.showToast('Đã tạo kho tài liệu!', 'success');
        app.renderVaults();
      } else {
        errorEl.textContent = resp.error?.message || 'Lỗi tạo kho.';
        errorEl.style.display = 'block';
      }
    } catch (err) {
      errorEl.textContent = `Lỗi: ${err.message}`;
      errorEl.style.display = 'block';
    } finally {
      btn.disabled = false;
      btn.textContent = 'Tạo';
    }
  },

  copyCitation(ref) {
    if (!ref) { app.showToast('Không có thông tin trích dẫn.', 'warning'); return; }
    navigator.clipboard.writeText(ref).then(() => {
      app.showToast('Đã sao chép trích dẫn!', 'success');
    }).catch(() => {
      app.showToast('Không thể sao chép.', 'error');
    });
  },

  // ------------------------------------------------------------------
  // Helpers
  // ------------------------------------------------------------------

  showToast(message, type = 'info', duration = 3000) {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.setAttribute('role', 'alert');
    toast.innerHTML = message;
    container.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transition = 'opacity 0.3s';
      setTimeout(() => toast.remove(), 300);
    }, duration);
  },

  esc(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  },

  parseTags(value) {
    const seen = new Set();
    return String(value || '')
      .split(/[,\n]/)
      .map(tag => tag.trim().replace(/\s+/g, ' '))
      .filter(tag => {
        const key = tag.toLocaleLowerCase('vi');
        if (!tag || seen.has(key)) return false;
        seen.add(key);
        return true;
      });
  },

  highlight(text, query) {
    if (!query || !text) return text || '';
    const terms = query.split(/\s+/).filter(t => t.length > 1);
    let result = text;
    terms.forEach(term => {
      const re = new RegExp(`(${term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
      result = result.replace(re, '<mark>$1</mark>');
    });
    return result;
  },

  renderMarkdown(text) {
    if (!text) return '';
    // Escape HTML first
    let result = text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
    // Then apply markdown formatting
    result = result
      .replace(/### (.+)/g, '<h3>$1</h3>')
      .replace(/## (.+)/g, '<h2>$1</h2>')
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.+?)\*/g, '<em>$1</em>')
      .replace(/^- (.+)/gm, '<li>$1</li>')
      .replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>')
      .replace(/\n{2,}/g, '</p><p>')
      .replace(/\n/g, '<br>');
    // Wrap in paragraph if not already wrapped
    if (!result.startsWith('<h') && !result.startsWith('<p')) {
      result = '<p>' + result + '</p>';
    }
    return result;
  },
};

// ------------------------------------------------------------------
// Auth module
// ------------------------------------------------------------------

class AuthModule {
  async handleLogin(event) {
    event.preventDefault();
    const user = document.getElementById('loginUser').value.trim();
    const pass = document.getElementById('loginPass').value;
    const errorEl = document.getElementById('loginError');
    const btn = event.target.querySelector('button[type="submit"]');

    if (!user || !pass) {
      errorEl.textContent = 'Vui lòng nhập tên đăng nhập và mật khẩu.';
      errorEl.style.display = 'block';
      return false;
    }

    errorEl.style.display = 'none';
    if (btn) btn.disabled = true;
    try {
      const resp = await api.login(user, pass);
      if (resp.success) {
        this.onLogin(user);
      } else {
        errorEl.textContent = resp.error?.message || 'Đăng nhập thất bại.';
        errorEl.style.display = 'block';
      }
    } catch (err) {
      errorEl.textContent = `Lỗi kết nối: ${err.message}`;
      errorEl.style.display = 'block';
    } finally {
      if (btn) btn.disabled = false;
    }
    return false;
  }

  onLogin(userOrId, navigate = true) {
    const user = typeof userOrId === 'string' ? { user_id: userOrId } : userOrId;
    document.getElementById('loginModal').style.display = 'none';
    document.getElementById('userName').textContent = user.user_id;
    document.getElementById('logoutBtn').style.display = 'inline-block';
    app.state.user = user;
    if (navigate) app.router.handleRoute();
  }

  logout() {
    api.logout();
    app.state.user = null;
    document.getElementById('userName').textContent = 'Chưa đăng nhập';
    document.getElementById('logoutBtn').style.display = 'none';
    document.getElementById('loginModal').style.display = 'flex';
    app.showToast('Đã đăng xuất.', 'info');
  }
}

// ------------------------------------------------------------------
// Router
// ------------------------------------------------------------------

class Router {
  constructor() {
    this.routes = {
      'home': () => app.renderHome(),
      'search': () => app.renderSearch(),
      'ask': () => app.renderAsk(),
      'vaults': () => app.renderVaults(),
      'documents': (params) => app.renderDocuments(params),
      'upload': () => app.renderUpload(),
      'admin': () => app.renderAdmin(),
      'setup': () => app.renderSetup(),
    };
  }

  navigate(page, queryString = '') {
    const hash = queryString ? `#/${page}?${queryString}` : `#/${page}`;
    window.location.hash = hash;
  }

  handleRoute() {
    if (!app.state.user) return;

    const hash = window.location.hash.slice(1) || '/home';
    const [path, queryString] = hash.split('?');
    const page = path.replace(/^\//, '') || 'home';

    const params = {};
    if (queryString) {
      queryString.split('&').forEach(pair => {
        const [k, v] = pair.split('=');
        if (k && v) params[k] = decodeURIComponent(v);
      });
    }

    if (this.routes[page]) {
      app.showPage(page);
      this.routes[page](params);
    } else {
      app.showPage('home');
      this.routes['home']();
    }
  }
}

// ------------------------------------------------------------------
// Start
// ------------------------------------------------------------------

document.addEventListener('DOMContentLoaded', () => app.init());
