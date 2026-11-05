const FALLBACK_ICON = 'other';
const STATUS_LABEL = { green: 'on track', yellow: 'ok', red: 'overdue' };
const CONFIRM_TIMEOUT_MS = 3000;

function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
}

function iconImg(name, className) {
    const img = el('img', className);
    img.alt = '';
    img.src = `${ICON_BASE}${name || FALLBACK_ICON}.png`;
    img.onerror = () => { img.onerror = null; img.src = `${ICON_BASE}${FALLBACK_ICON}.png`; };
    return img;
}

function timeAgo(ageDays) {
    if (ageDays < 1 / 24) return 'just now';
    if (ageDays < 1) return `${Math.floor(ageDays * 24)}h ago`;
    const days = Math.floor(ageDays);
    return days === 1 ? 'yesterday' : `${days} days ago`;
}

/* ---------- suggestions ---------- */
function suggestionRow(item, detail) {
    const row = el('div', `suggestion ${item.status}`);
    row.appendChild(iconImg(item.icon, 'suggestion-icon'));
    row.appendChild(el('span', 'suggestion-name', item.string));
    row.appendChild(el('span', 'suggestion-detail', detail));
    return row;
}

function renderSuggestions(sug) {
    const box = document.getElementById('suggestions');
    box.innerHTML = '';
    box.appendChild(el('h2', null, 'Priorities'));

    const before = el('div', 'suggestion-group');
    before.appendChild(el('h3', null, 'Do before it turns red'));
    sug.before_red.forEach(t => before.appendChild(suggestionRow(t, `${t.days_left}d left`)));
    if (!sug.before_red.length) before.appendChild(el('p', 'muted', 'Nothing close to red.'));
    box.appendChild(before);

    const overdue = el('div', 'suggestion-group');
    overdue.appendChild(el('h3', null, 'Overdue the longest'));
    sug.overdue.forEach(t => overdue.appendChild(suggestionRow(t, `${t.days_overdue}d late`)));
    if (!sug.overdue.length) overdue.appendChild(el('p', 'muted', 'Nothing overdue!'));
    box.appendChild(overdue);
}

/* ---------- task list ---------- */
function statusStrip(strip) {
    const wrap = el('div', 'status-strip');
    strip.forEach(day => {
        const box = el('span', `strip-box ${day.status || 'unknown'}`);
        box.title = `${day.date}: ${day.status ? STATUS_LABEL[day.status] : 'no data'}`;
        wrap.appendChild(box);
    });
    return wrap;
}

function doneButton(task) {
    const btn = el('button', 'done-button');
    btn.title = 'Mark as done';
    const idle = () => { btn.classList.remove('armed'); btn.replaceChildren(iconImg('done', 'done-icon')); };
    let timer = null;
    idle();
    btn.addEventListener('click', async () => {
        if (!btn.classList.contains('armed')) {
            btn.classList.add('armed');
            btn.textContent = 'Confirm';
            timer = setTimeout(idle, CONFIRM_TIMEOUT_MS);
            return;
        }
        clearTimeout(timer);
        btn.disabled = true;
        const res = await fetch(`/api/tasks/${task.id}/refresh`, { method: 'POST' });
        if (res.ok) loadAll(); else { btn.disabled = false; idle(); alert('Could not save, try again.'); }
    });
    return btn;
}

function taskCard(task) {
    const card = el('li', `task-card ${task.status}`);
    card.dataset.id = task.id;
    card.appendChild(iconImg(task.icon, 'task-icon'));

    const main = el('div', 'task-main');
    main.appendChild(el('div', 'task-name', task.string));
    const meta = el('div', 'task-meta');
    meta.appendChild(el('span', null, `On time: ${task.on_time_pct === null ? '–' : task.on_time_pct + '%'}`));
    meta.appendChild(el('span', null, `Last done: ${timeAgo(task.age_days)}`));
    main.appendChild(meta);
    main.appendChild(statusStrip(task.strip));
    card.appendChild(main);

    card.appendChild(doneButton(task));
    return card;
}

function renderTasks(tasks) {
    const list = document.getElementById('task-list');
    list.innerHTML = '';
    if (!tasks.length) {
        list.appendChild(el('li', 'muted empty', 'No tasks yet. Add some on the Edit page.'));
        return;
    }
    // most urgent first: least time left until it turns red
    [...tasks]
        .sort((a, b) => (a.lifespan - a.age_days) - (b.lifespan - b.age_days))
        .forEach(t => list.appendChild(taskCard(t)));
}

/* ---------- interim statistics (replaced in the statistics block) ---------- */
function renderDistribution(dist) {
    const box = document.getElementById('stats-bars');
    box.innerHTML = '';
    const max = Math.max(1, dist.green, dist.yellow, dist.red);
    ['green', 'yellow', 'red'].forEach(color => {
        const row = el('div', 'stat-bar-wrapper');
        const bar = el('div', `stat-bar ${color}`);
        bar.style.width = `${(dist[color] / max) * 200}px`;
        row.appendChild(bar);
        row.appendChild(el('span', 'stat-count', dist[color]));
        box.appendChild(row);
    });
}

function renderOldest(oldest) {
    const box = document.getElementById('oldest-tasks-list');
    box.innerHTML = '';
    oldest.slice(0, 2).forEach(t => {
        const row = el('div', `oldest-task ${t.status}`);
        row.appendChild(el('div', 'oldest-task-title', t.string));
        row.appendChild(el('div', 'oldest-task-info', `${t.age_days} days ago`));
        box.appendChild(row);
    });
    if (!oldest.length) box.appendChild(el('p', 'muted', 'No tasks yet'));
}

/* ---------- data + tabs ---------- */
async function loadAll() {
    const [tasks, stats] = await Promise.all([
        fetch('/api/tasks').then(r => r.json()),
        fetch('/api/stats?range=30').then(r => r.json()),
    ]);
    renderSuggestions(stats.suggestions);
    renderTasks(tasks);
    renderDistribution(stats.distribution);
    renderOldest(stats.oldest);
}

function setupTabs() {
    const home = document.getElementById('home');
    const buttons = document.querySelectorAll('.tab-button');
    const select = tab => {
        home.dataset.activeTab = tab;
        buttons.forEach(b => b.classList.toggle('active', b.dataset.tab === tab));
        localStorage.setItem('homeTab', tab);
    };
    buttons.forEach(b => b.addEventListener('click', () => select(b.dataset.tab)));
    select(localStorage.getItem('homeTab') === 'stats' ? 'stats' : 'tasks');
}

setupTabs();
loadAll();
