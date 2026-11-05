const FALLBACK_ICON = 'other';
const STATUS_LABEL = { green: 'on track', yellow: 'ok', red: 'overdue' };
const CONFIRM_TIMEOUT_MS = 3000;

let tasks = [];
let editing = null;   // task currently open in the modal

const $ = id => document.getElementById(id);

function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
}

function iconSrc(name) { return `${ICON_BASE}${name || FALLBACK_ICON}.png`; }

function iconImg(name, className) {
    const img = el('img', className);
    img.alt = '';
    img.src = iconSrc(name);
    img.onerror = () => { img.onerror = null; img.src = iconSrc(null); };
    return img;
}

function timeAgo(ageDays) {
    if (ageDays < 1 / 24) return 'just now';
    if (ageDays < 1) return `${Math.floor(ageDays * 24)}h ago`;
    const days = Math.floor(ageDays);
    return days === 1 ? 'yesterday' : `${days} days ago`;
}

function frequencyText(days) {
    if (days === 1) return 'daily';
    if (days === 7) return 'weekly';
    return `every ${days} days`;
}

const datePart = timestamp => timestamp.slice(0, 10);

/* ---------- table ---------- */
function renderRows() {
    const box = $('task-rows');
    box.innerHTML = '';
    if (!tasks.length) {
        box.appendChild(el('p', 'muted empty', 'No tasks yet. Add the first one above.'));
        return;
    }
    tasks.forEach(task => {
        const row = el('button', 'task-row');
        row.type = 'button';
        row.setAttribute('role', 'row');

        const name = el('span', 'cell-task');
        name.appendChild(iconImg(task.icon, 'row-icon'));
        name.appendChild(el('span', 'row-name', task.string));
        row.appendChild(name);

        const status = el('span', 'cell-status');
        const square = el('span', `status-square ${task.status}`);
        square.title = STATUS_LABEL[task.status];
        status.appendChild(square);
        row.appendChild(status);

        const last = el('span', 'cell-last');
        last.appendChild(el('span', null, datePart(task.last_refreshed)));
        last.appendChild(el('span', 'muted small', timeAgo(task.age_days)));
        row.appendChild(last);

        row.appendChild(el('span', 'cell-frequency', frequencyText(task.lifespan)));
        row.addEventListener('click', () => openModal(task));
        box.appendChild(row);
    });
}

async function loadTasks() {
    tasks = await fetch('/api/tasks').then(r => r.json());
    renderRows();
}

/* ---------- add form ---------- */
function validNew() {
    return $('new-item').value.trim() !== '' && parseFloat($('new-lifespan').value) > 0;
}

function syncAddButton() {
    $('add-button').disabled = !validNew();
}

$('new-item').addEventListener('input', syncAddButton);
$('new-lifespan').addEventListener('input', syncAddButton);

$('add-form').addEventListener('submit', async e => {
    e.preventDefault();
    if (!validNew()) return;
    $('add-button').disabled = true;
    const res = await fetch('/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ string: $('new-item').value.trim(), lifespan: parseFloat($('new-lifespan').value) }),
    });
    if (res.ok) {
        $('new-item').value = '';
        $('new-lifespan').value = '';
        await loadTasks();
    } else {
        alert('Failed to add the task.');
    }
    syncAddButton();
});

/* ---------- modal ---------- */
let deleteTimer = null;

function resetDeleteButton() {
    clearTimeout(deleteTimer);
    const btn = $('modal-delete');
    btn.classList.remove('armed');
    btn.lastChild.textContent = ' Delete';
}

function showError(message) {
    $('modal-error').textContent = message || '';
    $('modal-error').classList.toggle('hidden', !message);
}

function isDirty() {
    if (!editing) return false;
    return $('edit-name').value.trim() !== editing.string
        || parseFloat($('edit-lifespan').value) !== editing.lifespan
        || $('edit-date').value !== datePart(editing.last_refreshed);
}

function syncSaveButton() {
    const valid = $('edit-name').value.trim() !== '' && parseFloat($('edit-lifespan').value) > 0 && $('edit-date').value !== '';
    $('modal-save').disabled = !(valid && isDirty());
}

function openModal(task) {
    editing = task;
    $('modal-icon').src = iconSrc(task.icon);
    $('edit-name').value = task.string;
    $('edit-lifespan').value = task.lifespan;
    $('edit-date').value = datePart(task.last_refreshed);
    $('edit-date').max = datePart(new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString());
    showError('');
    resetDeleteButton();
    syncSaveButton();
    $('modal').classList.remove('hidden');
    $('edit-name').focus();
}

function closeModal() {
    editing = null;
    resetDeleteButton();
    $('modal').classList.add('hidden');
}

['edit-name', 'edit-lifespan', 'edit-date'].forEach(id => $(id).addEventListener('input', syncSaveButton));

$('modal-save').addEventListener('click', async () => {
    if (!editing || $('modal-save').disabled) return;
    const payload = {};
    if ($('edit-name').value.trim() !== editing.string) payload.string = $('edit-name').value.trim();
    if (parseFloat($('edit-lifespan').value) !== editing.lifespan) payload.lifespan = parseFloat($('edit-lifespan').value);
    if ($('edit-date').value !== datePart(editing.last_refreshed)) payload.last_refreshed = $('edit-date').value;

    $('modal-save').disabled = true;
    const res = await fetch(`/api/tasks/${editing.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });
    if (res.ok) {
        closeModal();
        await loadTasks();
    } else {
        const body = await res.json().catch(() => ({}));
        showError(body.error || 'Could not save, try again.');
        syncSaveButton();
    }
});

$('modal-delete').addEventListener('click', async () => {
    const btn = $('modal-delete');
    if (!btn.classList.contains('armed')) {
        btn.classList.add('armed');
        btn.lastChild.textContent = ' Sure?';
        deleteTimer = setTimeout(resetDeleteButton, CONFIRM_TIMEOUT_MS);
        return;
    }
    resetDeleteButton();
    const res = await fetch(`/api/tasks/${editing.id}`, { method: 'DELETE' });
    if (res.ok) {
        closeModal();
        await loadTasks();
    } else {
        showError('Could not delete, try again.');
    }
});

$('modal-cancel').addEventListener('click', closeModal);
$('modal-close').addEventListener('click', closeModal);
$('modal').addEventListener('click', e => { if (e.target === $('modal')) closeModal(); });
document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && editing) closeModal();
    if (e.key === 'Enter' && editing && e.target.tagName === 'INPUT') $('modal-save').click();
});

loadTasks();
