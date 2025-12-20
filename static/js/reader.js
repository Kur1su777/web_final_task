const docId = window.__DOC_ID__;
const analysisPanel = document.getElementById('analysis-panel');
const tabButtons = document.querySelectorAll('.insight-pane .tab-button');
const compareTabButtons = document.querySelectorAll('.compare-insight-pane .tab-button');
const qaForm = document.getElementById('qa-form');
const qaInput = document.getElementById('qa-input');
const qaChat = document.getElementById('qa-chat');
const toggleAiBtn = document.getElementById('toggle-ai');
const toggleCompareBtn = document.getElementById('toggle-compare');
const readerLayout = document.getElementById('reader-layout');
const docViewer = document.getElementById('doc-viewer');
const thumbnailBar = document.querySelector('.thumbnail-bar');
const comparePane = document.getElementById('compare-pane');
const compareSelect = document.getElementById('compare-select');
const compareCanvas = document.getElementById('compare-canvas');
const compareAnalysisPanel = document.getElementById('compare-analysis-panel');

let analysisData = null;
let compareAnalysisData = null;
let aiOpened = false;
let compareActive = false;
let compareDocId = '';

function setAiState(open) {
    if (!readerLayout) return;
    aiOpened = open;
    readerLayout.classList.toggle('with-ai', open);
    if (toggleAiBtn) {
        toggleAiBtn.classList.toggle('active', open);
        toggleAiBtn.innerHTML = open
            ? '<i class="fa-regular fa-eye-slash"></i> 隐藏 AI 提问'
            : '<i class="fa-regular fa-comments"></i> AI 提问';
    }
    if (open && qaInput) {
        setTimeout(() => qaInput.focus(), 120);
    }
}

if (toggleAiBtn) {
    toggleAiBtn.addEventListener('click', () => {
        setAiState(!aiOpened);
    });
}

if (toggleCompareBtn) {
    toggleCompareBtn.addEventListener('click', () => {
        if (!readerLayout) return;
        if (compareActive) {
            setCompareState(false);
        } else {
            setCompareState(true);
            loadCompareOptions();
        }
    });
}

if (thumbnailBar) {
    thumbnailBar.addEventListener('click', event => {
        const btn = event.target.closest('.thumb');
        if (!btn) return;
        thumbnailBar.querySelectorAll('.thumb').forEach(el => el.classList.remove('active'));
        btn.classList.add('active');

        const pageIndex = Number(btn.dataset.index || 1);
        if (docViewer) {
            const baseUrl = docViewer.dataset.base
                || docViewer.getAttribute('data-base')
                || docViewer.src.split('#')[0];
            docViewer.src = `${baseUrl}#page=${pageIndex}`;
        }
    });
}

function setCompareState(active) {
    compareActive = active;
    readerLayout.classList.toggle('compare-mode', active);
    if (toggleCompareBtn) {
        toggleCompareBtn.innerHTML = active
            ? '<i class="fa-regular fa-rectangle-xmark"></i> 退出对比'
            : '<i class="fa-regular fa-copy"></i> 文章对比';
    }
    if (!active) {
        compareDocId = '';
        if (compareSelect) {
            compareSelect.value = '';
        }
        if (compareCanvas) {
            compareCanvas.innerHTML = '<div class="empty-state"><i class="fa-regular fa-file-lines"></i><p>请选择右侧文档以开始对比</p></div>';
        }
        resetCompareSummary();
    }
}

function loadCompareOptions() {
    if (!compareSelect) return;
    fetch('/api/documents')
        .then(res => res.json())
        .then(data => {
            if (!data.success) return;
            compareSelect.innerHTML = '<option value="">选择对比文档</option>';
            data.documents
                .filter(doc => doc.id !== docId)
                .forEach(doc => {
                    const option = document.createElement('option');
                    option.value = doc.id;
                    option.textContent = doc.original_name;
                    compareSelect.appendChild(option);
                });
        })
        .catch(() => {});
}

function renderCompareDocument(doc) {
    if (!compareCanvas) return;
    if (!doc) {
        compareCanvas.innerHTML = '<div class="empty-state"><i class="fa-regular fa-file-lines"></i><p>请选择右侧文档以开始对比</p></div>';
        return;
    }
    const filename = doc.filename || '';
    const lower = filename.toLowerCase();
    const fileUrl = `/uploads/${encodeURIComponent(filename)}`;

    if (lower.endsWith('.pdf')) {
        compareCanvas.innerHTML = `<iframe src="${fileUrl}#toolbar=1&navpanes=1&pagemode=bookmarks" title="${doc.original_name}"></iframe>`;
        return;
    }
    if (['.png', '.jpg', '.jpeg', '.gif', '.webp'].some(ext => lower.endsWith(ext))) {
        compareCanvas.innerHTML = `<img src="${fileUrl}" alt="${doc.original_name}">`;
        return;
    }
    if (['.txt', '.md', '.csv', '.json'].some(ext => lower.endsWith(ext))) {
        fetch(fileUrl)
            .then(res => res.text())
            .then(text => {
                compareCanvas.innerHTML = `<div class="compare-text">${text}</div>`;
            })
            .catch(() => {
                compareCanvas.innerHTML = '<div class="compare-text">该文件暂不支持预览，请下载查看。</div>';
            });
        return;
    }
    compareCanvas.innerHTML = '<div class="compare-text">该文件暂不支持对比预览，请下载查看。</div>';
}

function setCompareTabActive(type) {
    compareTabButtons.forEach(button => {
        button.classList.toggle('active', button.dataset.tab === type);
    });
}

function resetCompareSummary() {
    compareAnalysisData = null;
    setCompareTabActive('summary');
    if (compareAnalysisPanel) {
        compareAnalysisPanel.innerHTML = '<p class="muted">请选择右侧文档以开始对比</p>';
    }
}

function setCompareAnalysisContent(type) {
    if (!compareAnalysisPanel) return;
    if (!compareAnalysisData) {
        compareAnalysisPanel.innerHTML = '<p class="muted">请选择右侧文档以开始对比</p>';
        return;
    }
    const map = {
        summary: {
            title: '全文总结',
            content: (compareAnalysisData.summary && compareAnalysisData.summary.trim()) || '尚未生成总结内容。',
        },
        deep_read: {
            title: '文章精读',
            content: (compareAnalysisData.deep_read && compareAnalysisData.deep_read.trim()) || '尚未生成精读内容。',
        },
        translation: {
            title: '文章翻译',
            content: (compareAnalysisData.translation && compareAnalysisData.translation.trim()) || '尚未生成翻译内容。',
        },
        mindmap: {
            title: '思维导图',
            content: (compareAnalysisData.mindmap && compareAnalysisData.mindmap.trim()) || '尚未生成思维导图。',
        },
    };
    const current = map[type];
    compareAnalysisPanel.innerHTML = `
        <h4>${current.title}</h4>
        <p>${current.content.replace(/\n/g, '<br>')}</p>
    `;
}

if (compareSelect) {
    compareSelect.addEventListener('change', () => {
        const selectedId = compareSelect.value;
        compareDocId = selectedId;
        if (!selectedId) {
            renderCompareDocument(null);
            resetCompareSummary();
            return;
        }
        fetch(`/api/documents/${selectedId}`)
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    renderCompareDocument(data.document);
                }
            })
            .catch(() => {});

        if (compareAnalysisPanel) {
            compareAnalysisPanel.innerHTML = '<div class="loading"><span class="spinner"></span>正在调用 AI 解读...</div>';
        }
        fetch(`/api/documents/${selectedId}/analysis`)
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    compareAnalysisData = data.analysis;
                    setCompareTabActive('summary');
                    setCompareAnalysisContent('summary');
                } else if (compareAnalysisPanel) {
                    compareAnalysisPanel.innerHTML = `<p>${data.error || '分析失败，请稍后重试。'}</p>`;
                }
            })
            .catch(() => {
                if (compareAnalysisPanel) {
                    compareAnalysisPanel.innerHTML = '<p>获取分析失败，请检查网络。</p>';
                }
            });
    });
}

function setAnalysisContent(type) {
    if (!analysisData) return;
    const map = {
        summary: {
            title: '全文总结',
            content: (analysisData.summary && analysisData.summary.trim()) || '尚未生成总结内容。',
        },
        deep_read: {
            title: '文章精读',
            content: (analysisData.deep_read && analysisData.deep_read.trim()) || '尚未生成精读内容。',
        },
        translation: {
            title: '文章翻译',
            content: (analysisData.translation && analysisData.translation.trim()) || '尚未生成翻译内容。',
        },
        mindmap: {
            title: '思维导图',
            content: (analysisData.mindmap && analysisData.mindmap.trim()) || '尚未生成思维导图。',
        },
    };
    const current = map[type];
    analysisPanel.innerHTML = `
        <h4>${current.title}</h4>
        <p>${current.content.replace(/\n/g, '<br>')}</p>
    `;
}

function fetchAnalysis() {
    fetch(`/api/documents/${docId}/analysis`)
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                analysisData = data.analysis;
                setAnalysisContent('summary');
            } else {
                analysisPanel.innerHTML = `<p>${data.error || '分析失败，请稍后重试。'}</p>`;
            }
        })
        .catch(() => {
            analysisPanel.innerHTML = '<p>获取分析失败，请检查网络。</p>';
        });
}

tabButtons.forEach(button => {
    button.addEventListener('click', () => {
        tabButtons.forEach(btn => btn.classList.remove('active'));
        button.classList.add('active');
        const tab = button.dataset.tab;
        setAnalysisContent(tab);
    });
});

compareTabButtons.forEach(button => {
    button.addEventListener('click', () => {
        compareTabButtons.forEach(btn => btn.classList.remove('active'));
        button.classList.add('active');
        const tab = button.dataset.tab;
        setCompareAnalysisContent(tab);
    });
});

if (qaForm) {
    qaForm.addEventListener('submit', e => {
        e.preventDefault();
        const question = qaInput.value.trim();
        if (!question) return;

        if (!aiOpened) {
            setAiState(true);
        }

        renderBubble(question, 'user');
        qaInput.value = '';
        qaInput.focus();

        renderBubble('思考中...', 'assistant', true);

        const payload = { question };
        if (compareActive && compareDocId) {
            payload.compare_doc_id = compareDocId;
        }
        fetch(`/api/documents/${docId}/ask`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload),
        })
            .then(res => res.json())
            .then(data => {
                qaChat.removeChild(qaChat.lastElementChild);
                if (data.success) {
                    renderBubble(data.answer, 'assistant');
                } else {
                    renderBubble(data.error || '回答失败，请稍后重试', 'assistant');
                }
            })
            .catch(() => {
                qaChat.removeChild(qaChat.lastElementChild);
                renderBubble('回答失败，请检查网络', 'assistant');
            });
    });
}

function renderBubble(text, role = 'assistant', isLoading = false) {
    if (!qaChat) return;
    const bubble = document.createElement('div');
    bubble.className = `qa-bubble ${role}`;
    bubble.innerHTML = isLoading ? '<span class="spinner"></span>' : text.replace(/\n/g, '<br>');
    qaChat.appendChild(bubble);
    qaChat.scrollTop = qaChat.scrollHeight;
}

fetchAnalysis();
