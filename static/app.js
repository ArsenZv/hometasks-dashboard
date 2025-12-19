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

function calculateTaskStatistics() {
    const todoList = document.getElementById('todo-list');
    const items = todoList.querySelectorAll('li');
    
    let greenCount = 0;
    let yellowCount = 0;
    let redCount = 0;
    
    items.forEach(item => {
        if (item.classList.contains('green')) {
            greenCount++;
        } else if (item.classList.contains('yellow')) {
            yellowCount++;
        } else if (item.classList.contains('red')) {
            redCount++;
        }
    });
    
    return { green: greenCount, yellow: yellowCount, red: redCount };
}

function renderStatistics() {
    const stats = calculateTaskStatistics();
    const total = stats.green + stats.yellow + stats.red;
    
    if (total === 0) {
        document.getElementById('green-bar').style.width = '0%';
        document.getElementById('yellow-bar').style.width = '0%';
        document.getElementById('red-bar').style.width = '0%';
        document.getElementById('green-count').textContent = '0';
        document.getElementById('yellow-count').textContent = '0';
        document.getElementById('red-count').textContent = '0';
        return;
    }
    
    const maxWidth = 150; // Maximum width in pixels for the bars
    const greenWidth = (stats.green / total) * maxWidth;
    const yellowWidth = (stats.yellow / total) * maxWidth;
    const redWidth = (stats.red / total) * maxWidth;
    
    document.getElementById('green-bar').style.width = `${greenWidth}px`;
    document.getElementById('yellow-bar').style.width = `${yellowWidth}px`;
    document.getElementById('red-bar').style.width = `${redWidth}px`;
    
    document.getElementById('green-count').textContent = stats.green;
    document.getElementById('yellow-count').textContent = stats.yellow;
    document.getElementById('red-count').textContent = stats.red;
}

function findOldestTasks() {
    const todoList = document.getElementById('todo-list');
    const items = Array.from(todoList.querySelectorAll('li'));
    
    // Extract task data with refresh dates
    const tasksWithDates = items.map(item => {
        const titleAttr = item.getAttribute('title');
        const itemText = item.querySelector('.item-text')?.textContent || '';
        
        // Parse the title to get last_refreshed date
        const refreshMatch = titleAttr?.match(/Last refreshed: ([^\|]+)/);
        const lifespanMatch = titleAttr?.match(/Lifespan: ([^\s]+)/);
        
        let colorClass = 'red';
        if (item.classList.contains('green')) {
            colorClass = 'green';
        } else if (item.classList.contains('yellow')) {
            colorClass = 'yellow';
        }
        
        return {
            text: itemText,
            lastRefreshed: refreshMatch ? refreshMatch[1].trim() : '',
            lifespan: lifespanMatch ? lifespanMatch[1].trim() : '',
            colorClass: colorClass,
            date: refreshMatch ? new Date(refreshMatch[1].trim()) : null
        };
    });
    
    // Filter out invalid dates and sort by oldest first
    const validTasks = tasksWithDates.filter(task => task.date !== null && !isNaN(task.date.getTime()));
    validTasks.sort((a, b) => a.date - b.date);
    
    return validTasks.slice(0, 2); // Get the 2 oldest
}

function renderOldestTasks() {
    const oldestTasks = findOldestTasks();
    const container = document.getElementById('oldest-tasks-list');
    
    if (oldestTasks.length === 0) {
        container.innerHTML = '<div class="oldest-task-placeholder">No tasks yet</div>';
        return;
    }
    
    container.innerHTML = '';
    const now = new Date();
    
    oldestTasks.forEach(task => {
        const taskDiv = document.createElement('div');
        taskDiv.className = `oldest-task ${task.colorClass}`;
        
        const titleDiv = document.createElement('div');
        titleDiv.className = 'oldest-task-title';
        titleDiv.textContent = task.text;
        
        // Calculate days ago
        const daysDiff = (now - task.date) / (1000 * 60 * 60 * 24);
        const daysAgo = daysDiff.toFixed(1);
        
        const infoDiv = document.createElement('div');
        infoDiv.className = 'oldest-task-info';
        infoDiv.textContent = `${daysAgo} days ago`;
        
        taskDiv.appendChild(titleDiv);
        taskDiv.appendChild(infoDiv);
        container.appendChild(taskDiv);
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
    
    // Render statistics and oldest tasks
    renderStatistics();
    renderOldestTasks();
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

document.querySelectorAll('#todo-list li').forEach(item => {
    item.addEventListener('click', (e) => {
        // If the click originated from the info icon, do nothing (handled by stopPropagation in HTML, but good to be safe)
        if (e.target.classList.contains('info-icon')) return;

        const itemIndex = item.getAttribute('data-index');
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

// Dashboard toggle functionality
const dashboardToggle = document.getElementById('dashboard-toggle');
const dashboardRow = document.getElementById('dashboard-row');

if (dashboardToggle && dashboardRow) {
    // Function to update UI based on state
    const setDashboardState = (show) => {
        if (show) {
            dashboardRow.classList.remove('hidden');
            dashboardToggle.setAttribute('aria-expanded', 'true');
            dashboardToggle.innerHTML = '<span class="toggle-icon">▼</span> Hide Statistics';
            localStorage.setItem('dashboardOpen', 'true');
        } else {
            dashboardRow.classList.add('hidden');
            dashboardToggle.setAttribute('aria-expanded', 'false');
            dashboardToggle.innerHTML = '<span class="toggle-icon">▼</span> Show Statistics';
            localStorage.setItem('dashboardOpen', 'false');
        }
    };

    dashboardToggle.addEventListener('click', () => {
        const isHidden = dashboardRow.classList.contains('hidden');
        setDashboardState(isHidden);
    });
}
