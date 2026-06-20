/* ============================================================
   AutoReply Dashboard — vanilla JS client
   ============================================================ */

// ── State ────────────────────────────────────────────────────
let campaigns = [];
let pendingDeleteId = null;

// ── Init ─────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  setWebhookUrl();
  loadConfig();
  loadCampaigns();
  checkConnectionStatus();
});

// ── Tab switching ─────────────────────────────────────────────
function switchTab(tabName, btn) {
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  document.getElementById(`tab-${tabName}`).classList.add('active');
  btn.classList.add('active');
}

// ── Connection status ─────────────────────────────────────────
async function checkConnectionStatus() {
  const dot = document.getElementById('statusDot');
  const text = document.getElementById('statusText');
  try {
    const config = await apiFetch('/api/config');
    if (config.access_token && config.instagram_business_account_id) {
      dot.className = 'status-dot connected';
      text.textContent = 'Connected';
    } else {
      dot.className = 'status-dot';
      text.textContent = 'Not configured';
    }
  } catch {
    dot.className = 'status-dot error';
    text.textContent = 'Error';
  }
}

// ── Webhook URL helper ────────────────────────────────────────
function setWebhookUrl() {
  const base = window.location.origin;
  document.getElementById('webhookUrl').textContent = `${base}/webhook/instagram`;
}

function copyWebhookUrl() {
  const url = document.getElementById('webhookUrl').textContent;
  navigator.clipboard.writeText(url).then(() => showToast('Webhook URL copied'));
}

// ── Config ────────────────────────────────────────────────────
async function loadConfig() {
  try {
    const config = await apiFetch('/api/config');
    document.getElementById('accessToken').value = config.access_token || '';
    document.getElementById('pageId').value = config.page_id || '';
    document.getElementById('igAccountId').value = config.instagram_business_account_id || '';
  } catch (e) {
    console.error('Failed to load config', e);
  }
}

async function saveConfig() {
  const payload = {
    access_token: document.getElementById('accessToken').value.trim(),
    page_id: document.getElementById('pageId').value.trim(),
    instagram_business_account_id: document.getElementById('igAccountId').value.trim(),
  };
  try {
    await apiFetch('/api/config', { method: 'POST', body: payload });
    showConfigStatus('Credentials saved.', 'success');
    showToast('Credentials saved', 'success');
    checkConnectionStatus();
  } catch (e) {
    showConfigStatus(`Save failed: ${e.message}`, 'error');
  }
}

async function verifyConfig() {
  const payload = {
    access_token: document.getElementById('accessToken').value.trim(),
    page_id: document.getElementById('pageId').value.trim(),
    instagram_business_account_id: document.getElementById('igAccountId').value.trim(),
  };
  try {
    const result = await apiFetch('/api/config/verify', { method: 'POST', body: payload });
    const name = result.account?.name || result.account?.username || 'Account';
    showConfigStatus(`✓ Connected as "${name}"`, 'success');
  } catch (e) {
    showConfigStatus(`Connection failed: ${e.message}`, 'error');
  }
}

function showConfigStatus(msg, type) {
  const el = document.getElementById('configStatus');
  el.textContent = msg;
  el.className = `config-status ${type}`;
  el.classList.remove('hidden');
}

// ── Campaigns list ────────────────────────────────────────────
async function loadCampaigns() {
  try {
    campaigns = await apiFetch('/api/campaigns');
    renderCampaigns();
  } catch (e) {
    console.error('Failed to load campaigns', e);
  }
}

function renderCampaigns() {
  const container = document.getElementById('campaignList');
  const empty = document.getElementById('emptyCampaigns');

  if (campaigns.length === 0) {
    container.innerHTML = '';
    container.appendChild(empty);
    empty.classList.remove('hidden');
    return;
  }

  container.innerHTML = campaigns.map(c => campaignCardHTML(c)).join('');
}

function campaignCardHTML(c) {
  const thumbHTML = c.post_thumbnail_url
    ? `<img class="campaign-thumb" src="${escHtml(c.post_thumbnail_url)}" alt="Post thumbnail" onerror="this.style.display='none'">`
    : `<div class="campaign-thumb-placeholder">📷</div>`;

  const caption = c.post_caption
    ? escHtml(c.post_caption.slice(0, 80)) + (c.post_caption.length > 80 ? '…' : '')
    : `Post ID: ${escHtml(c.post_id)}`;

  const chips = c.keyword_list.map(k => `<span class="chip">${escHtml(k)}</span>`).join('');

  const badgeHTML = c.is_active
    ? `<span class="badge badge-active">● Active</span>`
    : `<span class="badge badge-inactive">Paused</span>`;

  return `
    <div class="campaign-card ${c.is_active ? '' : 'inactive'}" id="card-${c.id}">
      ${thumbHTML}
      <div class="campaign-body">
        <div class="campaign-title">Post ${escHtml(c.post_id)}</div>
        <div class="campaign-caption">${caption}</div>
        <div class="keyword-chips">${chips}</div>
      </div>
      <div class="campaign-actions">
        ${badgeHTML}
        <button class="btn btn-icon btn-sm" title="Toggle active" onclick="toggleCampaign(${c.id})">
          ${c.is_active ? '⏸' : '▶'}
        </button>
        <button class="btn btn-icon btn-sm" title="Edit" onclick="openModal('edit', ${c.id})">✏️</button>
        <button class="btn btn-icon btn-sm" title="Delete" onclick="openDeleteModal(${c.id})">🗑</button>
      </div>
    </div>`;
}

// ── Campaign modal ────────────────────────────────────────────
function openModal(mode, campaignId) {
  document.getElementById('campaignModal').classList.remove('hidden');
  clearModal();

  if (mode === 'edit' && campaignId) {
    const c = campaigns.find(x => x.id === campaignId);
    if (!c) return;
    document.getElementById('modalTitle').textContent = 'Edit campaign';
    document.getElementById('editCampaignId').value = c.id;
    document.getElementById('postId').value = c.post_id;
    document.getElementById('keywords').value = c.keywords;
    document.getElementById('commentReply').value = c.comment_reply;
    document.getElementById('dmMessage').value = c.dm_message;
    document.getElementById('isActive').checked = c.is_active;

    if (c.post_thumbnail_url || c.post_caption) {
      showPostPreview({
        thumbnail_url: c.post_thumbnail_url,
        caption: c.post_caption,
        media_type: '',
        permalink: '',
      });
    }
  } else {
    document.getElementById('modalTitle').textContent = 'New campaign';
  }
}

function clearModal() {
  document.getElementById('editCampaignId').value = '';
  document.getElementById('postId').value = '';
  document.getElementById('keywords').value = '';
  document.getElementById('commentReply').value = '';
  document.getElementById('dmMessage').value = '';
  document.getElementById('isActive').checked = true;
  document.getElementById('postPreview').classList.add('hidden');
}

function closeModal() {
  document.getElementById('campaignModal').classList.add('hidden');
}

function closeModalOnBackdrop(e) {
  if (e.target === document.getElementById('campaignModal')) closeModal();
}

async function saveCampaign() {
  const campaignId = document.getElementById('editCampaignId').value;
  const payload = {
    post_id: document.getElementById('postId').value.trim(),
    keywords: document.getElementById('keywords').value.trim(),
    comment_reply: document.getElementById('commentReply').value.trim(),
    dm_message: document.getElementById('dmMessage').value.trim(),
    is_active: document.getElementById('isActive').checked,
  };

  if (!payload.post_id || !payload.keywords || !payload.comment_reply || !payload.dm_message) {
    showToast('Please fill in all fields', 'error');
    return;
  }

  try {
    if (campaignId) {
      await apiFetch(`/api/campaigns/${campaignId}`, { method: 'PATCH', body: payload });
      showToast('Campaign updated', 'success');
    } else {
      await apiFetch('/api/campaigns', { method: 'POST', body: payload });
      showToast('Campaign created', 'success');
    }
    closeModal();
    loadCampaigns();
  } catch (e) {
    showToast(`Save failed: ${e.message}`, 'error');
  }
}

async function toggleCampaign(id) {
  try {
    const result = await apiFetch(`/api/campaigns/${id}/toggle`, { method: 'POST' });
    const c = campaigns.find(x => x.id === id);
    if (c) c.is_active = result.is_active;
    renderCampaigns();
    showToast(result.is_active ? 'Campaign activated' : 'Campaign paused');
  } catch (e) {
    showToast(`Toggle failed: ${e.message}`, 'error');
  }
}

// ── Post preview ──────────────────────────────────────────────
async function fetchPostPreview() {
  const postId = document.getElementById('postId').value.trim();
  if (!postId) return;

  try {
    const data = await apiFetch(`/api/post-preview?post_id=${encodeURIComponent(postId)}`);
    showPostPreview(data);

    // Pre-fill caption into campaign for storage
    const c = campaigns.find(x => x.post_id === postId);
    if (!c) {
      // Will be saved on form submit — store temporarily
      document.getElementById('postId').dataset.caption = data.caption || '';
      document.getElementById('postId').dataset.thumb = data.thumbnail_url || '';
    }
  } catch (e) {
    showToast(`Couldn't fetch post: ${e.message}`, 'error');
  }
}

function showPostPreview(data) {
  const wrap = document.getElementById('postPreview');
  document.getElementById('previewThumb').src = data.thumbnail_url || '';
  document.getElementById('previewCaption').textContent = data.caption ? data.caption.slice(0, 120) + '…' : '(no caption)';
  document.getElementById('previewType').textContent = data.media_type || 'POST';
  const link = document.getElementById('previewLink');
  if (data.permalink) {
    link.href = data.permalink;
    link.classList.remove('hidden');
  } else {
    link.classList.add('hidden');
  }
  wrap.classList.remove('hidden');
}

// ── Delete modal ──────────────────────────────────────────────
function openDeleteModal(id) {
  pendingDeleteId = id;
  document.getElementById('deleteModal').classList.remove('hidden');
}

function closeDeleteModal() {
  pendingDeleteId = null;
  document.getElementById('deleteModal').classList.add('hidden');
}

function closeDeleteModalOnBackdrop(e) {
  if (e.target === document.getElementById('deleteModal')) closeDeleteModal();
}

async function confirmDelete() {
  if (!pendingDeleteId) return;
  try {
    await apiFetch(`/api/campaigns/${pendingDeleteId}`, { method: 'DELETE' });
    showToast('Campaign deleted');
    closeDeleteModal();
    loadCampaigns();
  } catch (e) {
    showToast(`Delete failed: ${e.message}`, 'error');
  }
}

// ── Toast ─────────────────────────────────────────────────────
let toastTimer;
function showToast(msg, type = '') {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = `toast ${type}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.add('hidden'), 3500);
}

// ── API helper ────────────────────────────────────────────────
async function apiFetch(path, { method = 'GET', body } = {}) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
  };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(path, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
  return data;
}

// ── Escape HTML ───────────────────────────────────────────────
function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
