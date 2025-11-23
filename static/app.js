function determineLevel(count, totalTasks) {
    if (!totalTasks) {
        return 0;
    }
    const ratio = count / totalTasks;
    if (ratio >= 0.75) {
        return 4;
    }
    if (ratio >= 0.5) {
        return 3;
    }
    if (ratio >= 0.25) {
        return 2;
    }
    if (count > 0) {
        return 1;
    }
    return 0;
}

function renderCalendar(data, totalTasks) {
    const calendarElement = document.getElementById('refresh-calendar');
    if (!calendarElement || !Array.isArray(data) || data.length === 0) {
        return;
    }

    calendarElement.innerHTML = '';
    const firstDate = new Date(`${data[0].date}T00:00:00`);
    const leadingEmpty = firstDate.getDay();

    for (let i = 0; i < leadingEmpty; i += 1) {
        const spacer = document.createElement('span');
        spacer.className = 'day-cell empty';
        spacer.setAttribute('aria-hidden', 'true');
        calendarElement.appendChild(spacer);
    }

    data.forEach((entry) => {
        const cell = document.createElement('span');
        cell.classList.add('day-cell');
        const level = determineLevel(entry.count || 0, totalTasks);
        cell.classList.add(`level-${level}`);
        const dateObj = new Date(`${entry.date}T00:00:00`);
        const count = entry.count || 0;
        cell.title = `${count} refresh${count === 1 ? '' : 'es'} on ${dateObj.toLocaleDateString()}`;
        cell.setAttribute('aria-label', cell.title);
        calendarElement.appendChild(cell);
    });
}

document.addEventListener('DOMContentLoaded', () => {
    const todayDateElement = document.getElementById('today-date');
    const today = new Date();
    const formattedDate = `${String(today.getDate()).padStart(2, '0')}/${String(today.getMonth() + 1).padStart(2, '0')}/${String(today.getFullYear()).slice(-2)}`;
    todayDateElement.textContent = `Today: ${formattedDate}`;

    if (typeof CALENDAR_DATA !== 'undefined' && typeof TOTAL_TASKS !== 'undefined') {
        renderCalendar(CALENDAR_DATA, TOTAL_TASKS);
    }
});

document.getElementById('add-button').addEventListener('click', () => {
    const newString = document.getElementById('new-item').value;
    const newLifespan = parseFloat(document.getElementById('new-lifespan').value);
    if (newString && !isNaN(newLifespan)) {
        fetch('/add', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ string: newString, lifespan: newLifespan })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                location.reload();
            }
        });
    }
});

document.querySelectorAll('.refresh-icon').forEach(icon => {
    icon.addEventListener('click', () => {
        const itemIndex = icon.getAttribute('data-index');
        fetch(`/refresh/${itemIndex}`, {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                location.reload();
            }
        });
    });
});
