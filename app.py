from flask import Flask, render_template, request, jsonify
import json
from datetime import datetime

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.jinja_env.auto_reload = True

DATA_FILE = 'data.json'

def load_data():
    try:
        with open(DATA_FILE, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return []

def save_data(data):
    with open(DATA_FILE, 'w') as file:
        json.dump(data, file, indent=4)

@app.route('/')
def index():
    items = load_data()
    return render_template('index.html', items=items)

@app.route('/add', methods=['POST'])
def add_item():
    data = load_data()
    new_item = {
        'string': request.json.get('string'),
        'lifespan': request.json.get('lifespan'),
        'date_added': datetime.now().isoformat()
    }
    if new_item['string'] and isinstance(new_item['lifespan'], (int, float)):
        data.append(new_item)
        save_data(data)
        return jsonify({'success': True, 'items': data})
    return jsonify({'success': False}), 400

@app.route('/refresh/<int:item_index>', methods=['POST'])
def refresh_item(item_index):
    data = load_data()
    if 0 <= item_index < len(data):
        data[item_index]['date_added'] = datetime.now().isoformat()
        save_data(data)
        return jsonify({'success': True, 'item': data[item_index]})
    return jsonify({'success': False}), 400

if __name__ == '__main__':
    app.run(debug=True)