const ICONS = {
    pdf: `<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6z" stroke="#e74c3c" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M14 2v6h6" stroke="#e74c3c" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        <text x="12" y="17" text-anchor="middle" fill="#e74c3c" font-size="6" font-weight="bold">PDF</text>
    </svg>`,
    word: `<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6z" stroke="#2b579a" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M14 2v6h6" stroke="#2b579a" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        <text x="12" y="17" text-anchor="middle" fill="#2b579a" font-size="6" font-weight="bold">DOC</text>
    </svg>`,
    image: `<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect x="3" y="3" width="18" height="18" rx="2" ry="2" stroke="#27ae60" stroke-width="2"/>
        <circle cx="8.5" cy="8.5" r="1.5" fill="#27ae60"/>
        <polyline points="21 15 16 10 5 21" stroke="#27ae60" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>`,
    file: `<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6z" stroke="#95a5a6" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M14 2v6h6" stroke="#95a5a6" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>`
};

const loadingEl = document.getElementById('loading');
const errorEl = document.getElementById('error');
const filesContainer = document.getElementById('filesContainer');
const emptyState = document.getElementById('emptyState');

function show(el) {
    el.classList.remove('hidden');
}

function hide(el) {
    el.classList.add('hidden');
}

function showError(message) {
    errorEl.textContent = message;
    show(errorEl);
}

function hideError() {
    hide(errorEl);
}

function createFileRow(file) {
    const row = document.createElement('div');
    row.className = 'file-row';

    const pages = file.page_count || 1;

    row.innerHTML = `
        <div class="file-row-name">
            <div class="file-icon-small">${ICONS[file.icon] || ICONS.file}</div>
            <span>${file.name}</span>
        </div>
        <div class="file-row-pages">${pages} стр.</div>
        <button class="delete-btn" data-key="${file.key}">✕</button>
    `;

    row.querySelector('.delete-btn').addEventListener('click', () => handleDelete(file.key));
    return row;
}

async function handleDelete(key) {
    if (!confirm('Удалить файл?')) return;
    const parts = key.split('/');
    const telegramId = parts[0];
    const filename = parts.slice(1).join('/');

    try {
        const response = await fetch(`/api/files/${telegramId}/${filename}`, { method: 'DELETE' });
        if (response.ok) {
            loadFiles(telegramId);
        } else {
            const data = await response.json().catch(() => ({}));
            alert(data.detail || 'Ошибка удаления');
        }
    } catch (err) {
        alert('Ошибка удаления');
    }
}

async function loadFiles(telegramId) {
    hide(filesContainer);
    hide(emptyState);
    hideError();
    show(loadingEl);

    try {
        const response = await fetch(`/api/files/${telegramId}`);

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || 'Ошибка при загрузке файлов');
        }

        const data = await response.json();

        hide(loadingEl);

        if (data.files.length === 0) {
            show(emptyState);
            return;
        }

        filesContainer.innerHTML = '';
        data.files.forEach(file => {
            filesContainer.appendChild(createFileRow(file));
        });
        show(filesContainer);
    } catch (err) {
        hide(loadingEl);
        showError(err.message || 'Произошла ошибка при загрузке');
    }
}

const pathParts = window.location.pathname.split('/').filter(Boolean);
const telegramId = pathParts.length === 1 ? pathParts[0] : null;

const uploadSection = document.getElementById('uploadSection');
const fileInput = document.getElementById('fileInput');
const uploadBtn = document.getElementById('uploadBtn');

uploadBtn.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', handleUpload);

async function handleUpload() {
    const files = fileInput.files;
    if (!files.length) return;

    const ALLOWED = ['.doc', '.docx', '.pdf', '.png', '.jpg', '.jpeg'];
    const filtered = Array.from(files).filter(f => {
        const ext = '.' + f.name.split('.').pop().toLowerCase();
        return ALLOWED.includes(ext);
    });
    if (!filtered.length) {
        alert('Допустимые форматы: doc, docx, pdf, png, jpg, jpeg');
        fileInput.value = '';
        return;
    }

    const formData = new FormData();
    for (const f of filtered) formData.append('files', f);

    try {
        const response = await fetch(`/api/upload/${telegramId}`, { method: 'POST', body: formData });
        if (response.ok) {
            fileInput.value = '';
            loadFiles(telegramId);
        } else {
            const data = await response.json().catch(() => ({}));
            alert(data.detail || 'Ошибка загрузки');
        }
    } catch (err) {
        alert('Ошибка загрузки');
    }
}

if (telegramId) {
    loadFiles(telegramId);
    show(uploadSection);
}
