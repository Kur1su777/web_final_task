const docId = window.__DOC_ID__;
const analysisPanel = document.getElementById('analysis-panel');
const tabButtons = document.querySelectorAll('.tab-button');
const qaForm = document.getElementById('qa-form');
const qaInput = document.getElementById('qa-input');
const qaChat = document.getElementById('qa-chat');
const toggleAiBtn = document.getElementById('toggle-ai');
const readerLayout = document.getElementById('reader-layout');
const aiPane = document.getElementById('ai-pane');
const thumbnailBar = document.querySelector('.thumbnail-bar');

let analysisData = null;
let aiOpened = false;

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

if (thumbnailBar) {
    thumbnailBar.addEventListener('click', event => {
        const btn = event.target.closest('.thumb');
        if (!btn) return;
        thumbnailBar.querySelectorAll('.thumb').forEach(el => el.classList.remove('active'));
        btn.classList.add('active');
        // 如果需要，可在这里联动文档预览滚动逻辑。
    });
}

function setAnalysisContent(type) {
    if (!analysisData) return;
    const map = {
        category: {
            title: '智能分类',
            content: (analysisData.category && analysisData.category.trim()) || '分类模型暂未返回结果，稍后再试。',
        },
        summary: {
            title: '全文摘要',
            content: (analysisData.summary && analysisData.summary.trim()) || '尚未生成摘要内容。',
        },
        explanation: {
            title: '文档解读',
            content: (analysisData.explanation && analysisData.explanation.trim()) || '尚未生成解读内容。',
        },
    };
    const current = map[type];
    analysisPanel.innerHTML = `
        <h4>${current.title}</h4>
        <p>${current.content.replace(/
/g, '<br>')}</p>
    `;
}

function fetchAnalysis() {
    fetch(`/api/documents/${docId}/analysis`)
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                analysisData = data.analysis;
                setAnalysisContent('category');
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

        fetch(`/api/documents/${docId}/ask`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({question}),
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
    bubble.innerHTML = isLoading ? '<span class="spinner"></span>' : text.replace(/
/g, '<br>');
    qaChat.appendChild(bubble);
    qaChat.scrollTop = qaChat.scrollHeight;
}

fetchAnalysis();
