document.getElementById('add-button').addEventListener('click', () => {
    const newItem = document.getElementById('new-item').value;
    if (newItem) {
        fetch('/add', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ item: newItem })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const list = document.getElementById('todo-list');
                const listItem = document.createElement('li');
                listItem.textContent = newItem;
                list.appendChild(listItem);
                document.getElementById('new-item').value = '';
            }
        });
    }
});