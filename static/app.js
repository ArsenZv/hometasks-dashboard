document.addEventListener('DOMContentLoaded', () => {
    const todayDateElement = document.getElementById('today-date');
    const today = new Date();
    todayDateElement.textContent = `Today: ${today.toLocaleDateString()}`;
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