document.querySelectorAll('.delete-button').forEach(button => {
    button.addEventListener('click', () => {
        const itemIndex = button.getAttribute('data-index');
        fetch(`/delete/${itemIndex}`, {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                location.reload();
            } else {
                alert('Failed to delete the item.');
            }
        });
    });
});

document.getElementById('save-button').addEventListener('click', () => {
    // Collect updated data from inputs
    const updatedItems = [];
    document.querySelectorAll('#edit-list li').forEach((li, index) => {
        const string = li.querySelector('.edit-string').value;
        const lifespan = parseFloat(li.querySelector('.edit-lifespan').value);
        const dateAdded = li.querySelector('.edit-date').value;
        updatedItems.push({ string, lifespan, last_refreshed: dateAdded });
    });

    // Send updated data to the server
    fetch('/save', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ items: updatedItems })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            const message = document.getElementById('confirmation-message');
            message.style.display = 'block';
            setTimeout(() => {
                message.style.display = 'none';
            }, 3000);
        } else {
            alert('Failed to save changes.');
        }
    });
});

document.addEventListener('DOMContentLoaded', () => {
    const appVersion = process.env.APP_VERSION || 'Unknown';
    document.getElementById('app-version').textContent = `Current Version: ${appVersion}`;
});