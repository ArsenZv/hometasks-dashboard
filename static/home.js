const FALLBACK_ICON = 'other';
const STATUS_LABEL = { green: 'on track', yellow: 'ok', red: 'overdue' };

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
    box.appendChild(el('h2', null, 'Suggestions'));

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
    btn.appendChild(iconImg('done', 'done-icon'));
    btn.addEventListener('click', async () => {
        btn.disabled = true;
        const res = await fetch(`/api/tasks/${task.id}/refresh`, { method: 'POST' });
        if (res.ok) {
            loadAll();
        } else {
            btn.disabled = false;
            alert('Could not save, try again.');
        }
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

/* ---------- statistics ---------- */
const SVG_NS = 'http://www.w3.org/2000/svg';
const COLORS = { green: '#D5E8B0', yellow: '#F6D996', red: '#F5AAA1' };
const INK = '#432B23';
let currentRange = localStorage.getItem('statsRange') || '30';

function svg(tag, attrs) {
    const node = document.createElementNS(SVG_NS, tag);
    Object.entries(attrs || {}).forEach(([k, v]) => node.setAttribute(k, v));
    return node;
}

function legendItem(color, label) {
    const item = el('span', 'legend-item');
    const swatch = el('span', 'legend-swatch');
    swatch.style.background = color;
    item.appendChild(swatch);
    item.appendChild(document.createTextNode(label));
    return item;
}

function renderProgress(p) {
    const box = document.getElementById('progress');
    box.innerHTML = '';
    const bar = el('div', 'progress-bar');
    [['green', p.green], ['yellow', p.yellow]].forEach(([color, pct]) => {
        const seg = el('div', 'progress-seg');
        seg.style.width = `${pct}%`;
        seg.style.background = COLORS[color];
        seg.title = `${color}: ${pct}%`;
        bar.appendChild(seg);
    });
    box.appendChild(bar);
    const legend = el('div', 'legend');
    legend.appendChild(legendItem(COLORS.green, `Done in time ${p.green}%`));
    legend.appendChild(legendItem(COLORS.yellow, `Still OK ${p.yellow}%`));
    legend.appendChild(legendItem('#E5D9CA', `Overdue ${p.red}%`));
    box.appendChild(legend);
    const total = Math.round((p.green + p.yellow) * 10) / 10;
    box.appendChild(el('p', 'big-number', `${total}% of the time everything was under control`));
}

function arcPath(cx, cy, rOuter, rInner, a0, a1) {
    const pt = (r, a) => [cx + r * Math.sin(a), cy - r * Math.cos(a)];
    const large = a1 - a0 > Math.PI ? 1 : 0;
    const [x0, y0] = pt(rOuter, a0), [x1, y1] = pt(rOuter, a1);
    const [x2, y2] = pt(rInner, a1), [x3, y3] = pt(rInner, a0);
    return `M${x0} ${y0} A${rOuter} ${rOuter} 0 ${large} 1 ${x1} ${y1} L${x2} ${y2} A${rInner} ${rInner} 0 ${large} 0 ${x3} ${y3} Z`;
}

function renderDonut(dist) {
    const box = document.getElementById('donut');
    box.innerHTML = '';
    const total = dist.green + dist.yellow + dist.red;
    const chart = svg('svg', { viewBox: '0 0 160 160', class: 'donut-svg', role: 'img' });
    const [cx, cy, ro, ri] = [80, 80, 74, 42];

    if (!total) {
        chart.appendChild(svg('circle', { cx, cy, r: (ro + ri) / 2, fill: 'none', stroke: '#E5D9CA', 'stroke-width': ro - ri }));
    } else {
        let angle = 0;
        ['green', 'yellow', 'red'].filter(c => dist[c] > 0).forEach(color => {
            const span = (dist[color] / total) * Math.PI * 2;
            const full = dist[color] === total;
            // a full ring can't be one arc: draw two halves
            const parts = full ? [[0, Math.PI], [Math.PI, Math.PI * 2]] : [[angle, angle + span]];
            parts.forEach(([a0, a1]) => chart.appendChild(svg('path', {
                d: arcPath(cx, cy, ro, ri, a0, a1), fill: COLORS[color], stroke: INK, 'stroke-width': 3, 'stroke-linejoin': 'miter'
            })));
            angle += span;
        });
    }
    const label = svg('text', { x: cx, y: cy + 8, 'text-anchor': 'middle', class: 'donut-total' });
    label.textContent = total;
    chart.appendChild(label);
    box.appendChild(chart);

    const legend = el('div', 'legend');
    ['green', 'yellow', 'red'].forEach(c => legend.appendChild(legendItem(COLORS[c], `${dist[c]} ${STATUS_LABEL[c]}`)));
    box.appendChild(legend);
}

function renderOldest(oldest) {
    const box = document.getElementById('oldest-tasks-list');
    box.innerHTML = '';
    oldest.slice(0, 2).forEach(t => {
        const row = el('div', `oldest-task ${t.status}`);
        row.appendChild(iconImg(t.icon, 'suggestion-icon'));
        const text = el('div', 'oldest-text');
        text.appendChild(el('div', 'oldest-task-title', t.string));
        text.appendChild(el('div', 'oldest-task-info', timeAgo(t.age_days)));
        row.appendChild(text);
        box.appendChild(row);
    });
    if (!oldest.length) box.appendChild(el('p', 'muted', 'No tasks yet'));
}

function renderHighlight(id, task, describe) {
    const box = document.getElementById(id);
    box.innerHTML = '';
    if (!task) { box.appendChild(el('p', 'muted', 'No tasks yet')); return; }
    const card = el('div', 'highlight');
    card.appendChild(iconImg(task.icon, 'highlight-icon'));
    const text = el('div', 'highlight-text');
    text.appendChild(el('div', 'highlight-name', task.string));
    text.appendChild(el('div', 'muted small', describe(task)));
    card.appendChild(text);
    box.appendChild(card);
}

function describeEase(t) {
    const every = t.lifespan === 1 ? 'every day' : `every ${t.lifespan} days`;
    return `done ${t.completions}x, due ${every} (${t.ease}x of needed)`;
}

function renderProcrastination(p) {
    const box = document.getElementById('procrastination');
    box.innerHTML = '';
    if (!p.longest) {
        box.appendChild(el('p', 'big-number', 'No procrastination in this period!'));
        return;
    }
    const counts = new Map(p.histogram.map(h => [h.length, h.count]));
    const bins = Array.from({ length: p.longest }, (_, i) => ({ length: i + 1, count: counts.get(i + 1) || 0 }));
    const maxCount = Math.max(...bins.map(b => b.count));

    const [W, H, padL, padB, padT] = [Math.max(320, bins.length * 34 + 50), 170, 34, 30, 14];
    const chart = svg('svg', { viewBox: `0 0 ${W} ${H}`, class: 'hist-svg', role: 'img' });
    const plotH = H - padB - padT;
    const bw = (W - padL - 8) / bins.length;

    for (let v = 0; v <= maxCount; v += 1) {
        const y = padT + plotH - (v / maxCount) * plotH;
        chart.appendChild(svg('line', { x1: padL, x2: W - 8, y1: y, y2: y, stroke: '#CDA98A', 'stroke-width': 1, 'stroke-dasharray': '3 3' }));
        const t = svg('text', { x: padL - 6, y: y + 4, 'text-anchor': 'end', class: 'axis-text' });
        t.textContent = v;
        chart.appendChild(t);
    }
    bins.forEach((b, i) => {
        const h = (b.count / maxCount) * plotH;
        const x = padL + i * bw + 4;
        if (b.count) {
            const bar = svg('rect', { x, y: padT + plotH - h, width: bw - 8, height: h, fill: COLORS.red, stroke: INK, 'stroke-width': 3 });
            const tip = svg('title', {});
            tip.textContent = `${b.count} period(s) of ${b.length} day(s)`;
            bar.appendChild(tip);
            chart.appendChild(bar);
        }
        const t = svg('text', { x: x + (bw - 8) / 2, y: H - 12, 'text-anchor': 'middle', class: 'axis-text' });
        t.textContent = b.length;
        chart.appendChild(t);
    });
    chart.appendChild(svg('line', { x1: padL, x2: W - 8, y1: padT + plotH, y2: padT + plotH, stroke: INK, 'stroke-width': 3 }));
    box.appendChild(chart);
    box.appendChild(el('p', 'axis-caption', 'x: length of the streak (days) · y: how many times'));
    box.appendChild(el('p', 'big-number',
        `Longest: ${p.longest} day${p.longest === 1 ? '' : 's'}` + (p.current ? ` · happening now: ${p.current}` : '')));
}

function renderStats(stats) {
    renderProgress(stats.progress);
    renderDonut(stats.distribution);
    renderOldest(stats.oldest);
    renderHighlight('easiest', stats.easiest[0], describeEase);
    renderHighlight('hated', stats.hated[0], describeEase);
    renderProcrastination(stats.procrastination);
}

/* ---------- data + tabs ---------- */
async function loadAll() {
    const [tasks, stats] = await Promise.all([
        fetch('/api/tasks').then(r => r.json()),
        fetch(`/api/stats?range=${currentRange}`).then(r => r.json()),
    ]);
    renderSuggestions(stats.suggestions);
    renderTasks(tasks);
    renderStats(stats);
}

function setupRange() {
    const buttons = document.querySelectorAll('.range-button');
    const mark = () => buttons.forEach(b => b.classList.toggle('active', b.dataset.range === currentRange));
    buttons.forEach(b => b.addEventListener('click', () => {
        currentRange = b.dataset.range;
        localStorage.setItem('statsRange', currentRange);
        mark();
        loadAll();
    }));
    mark();
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
setupRange();
loadAll();
