const dropzone = document.getElementById('dropzone');
const fileInput = document.getElementById('file-input');
const browseBtn = document.getElementById('browse-files');
const recentList = document.getElementById('recent-list');
const linkModal = document.getElementById('link-modal');
const clearHistoryBtn = document.getElementById('clear-history');
const linkTriggers = [document.getElementById('paste-link'), document.getElementById('open-history')];
const linkInput = document.getElementById('link-input');
const importLinkBtn = document.getElementById('import-link-btn');

function openModal(modal) {
    modal.classList.add('active');
}

function closeModal(modal) {
    modal.classList.remove('active');
}

if (dropzone) {
    ['dragenter', 'dragover'].forEach(evt => {
        dropzone.addEventListener(evt, event => {
            event.preventDefault();
            event.dataTransfer.dropEffect = 'copy';
            dropzone.classList.add('dragover');
        });
    });

    ['dragleave', 'drop'].forEach(evt => {
        dropzone.addEventListener(evt, event => {
            event.preventDefault();
            dropzone.classList.remove('dragover');
        });
    });

    dropzone.addEventListener('drop', event => {
        const files = event.dataTransfer.files;
        if (files && files.length) {
            uploadFile(files[0]);
        }
    });

    dropzone.addEventListener('click', event => {
        if (event.target.closest('input')) return;
        if (fileInput) {
            fileInput.click();
        }
    });
}

if (browseBtn) {
    browseBtn.addEventListener('click', () => fileInput.click());
}

if (fileInput) {
    fileInput.addEventListener('change', () => {
        if (fileInput.files && fileInput.files.length) {
            uploadFile(fileInput.files[0]);
            fileInput.value = '';
        }
    });
}

function removeCardElement(card) {
    if (!card || !recentList) return;
    card.remove();
    if (!recentList.querySelector('.recent-item')) {
        recentList.innerHTML = '<div class="empty-state"><i class="fa-regular fa-box-open"></i><p>暂无上传记录，立即体验智能阅读吧！</p></div>';
    }
}

function deleteDocument(id, card) {
    fetch(`/api/documents/${id}`, { method: 'DELETE' })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                removeCardElement(card);
                showToast('已删除该记录');
            } else {
                showToast(data.error || '删除失败');
            }
        })
        .catch(() => showToast('删除失败，请检查网络'));
}

if (recentList) {
    recentList.addEventListener('click', e => {
        const deleteBtn = e.target.closest('.recent-delete');
        const openBtn = e.target.closest('.recent-open');
        const card = e.target.closest('.recent-item');
        if (!card) return;

        if (deleteBtn) {
            deleteDocument(card.dataset.id, card);
            return;
        }

        if (openBtn || !e.target.closest('.recent-actions-inline')) {
            window.location.href = `/reader/${card.dataset.id}`;
        }
    });
}

if (clearHistoryBtn) {
    clearHistoryBtn.addEventListener('click', () => {
        if (!recentList || !recentList.querySelector('.recent-item')) {
            showToast('暂无记录可清空');
            return;
        }
        fetch('/api/documents/clear', { method: 'POST' })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    recentList.innerHTML = '<div class="empty-state"><i class="fa-regular fa-box-open"></i><p>暂无上传记录，立即体验智能阅读吧！</p></div>';
                    showToast('历史记录已清空');
                } else {
                    showToast(data.error || '清空失败');
                }
            })
            .catch(() => showToast('清空失败，请检查网络'));
    });
}

if (linkModal) {
    document.querySelectorAll('[data-close]').forEach(btn => {
        btn.addEventListener('click', () => closeModal(linkModal));
    });
    linkTriggers.forEach(btn => {
        if (btn) {
            btn.addEventListener('click', () => openModal(linkModal));
        }
    });
}

function uploadFile(file) {
    const formData = new FormData();
    formData.append('file', file);

    dropzone.classList.add('uploading');
    dropzone.querySelector('p').textContent = `正在上传 ${file.name}...`;

    fetch('/upload', {
        method: 'POST',
        body: formData,
    })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                window.location.href = data.redirect;
            } else {
                showToast(data.error || '上传失败，请重试');
            }
        })
        .catch(() => {
            showToast('上传失败，请检查网络后重试');
        })
        .finally(() => {
            dropzone.classList.remove('uploading');
            dropzone.querySelector('p').textContent = '将文件拖入 / 点击选择';
        });
}

function showToast(message) {
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = message;
    document.body.appendChild(toast);
    requestAnimationFrame(() => toast.classList.add('visible'));
    setTimeout(() => {
        toast.classList.remove('visible');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

function setImportButtonLoading(loading) {
    if (!importLinkBtn) return;
    importLinkBtn.disabled = loading;
    importLinkBtn.classList.toggle('disabled', loading);
    importLinkBtn.textContent = loading ? '正在导入...' : '开始导入';
}

function importFromLink() {
    const url = (linkInput && linkInput.value || '').trim();
    if (!url) {
        showToast('请输入有效的链接');
        return;
    }

    setImportButtonLoading(true);
    fetch('/api/import_url', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
    })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                window.location.href = data.redirect;
                return;
            }
            showToast(data.error || '导入失败，请重试');
        })
        .catch(() => showToast('导入失败，请检查网络后重试'))
        .finally(() => setImportButtonLoading(false));
}

if (importLinkBtn) {
    importLinkBtn.addEventListener('click', importFromLink);
}

if (linkInput) {
    linkInput.addEventListener('keydown', e => {
        if (e.key === 'Enter') {
            e.preventDefault();
            importFromLink();
        }
    });
}
