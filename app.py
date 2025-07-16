from flask import Flask, render_template, request, jsonify
import json
from datetime import datetime, timedelta
from subprocess import check_output
import os

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.jinja_env.auto_reload = True

# Custom Jinja2 filter to convert string to datetime
@app.template_filter('to_datetime')
def to_datetime(value):
    return datetime.strptime(value, '%Y-%m-%dT%H:%M:%S')

DATA_FILE = 'data/data.json'

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
    current_time = datetime.now()
    return render_template('index.html', items=items, current_time=current_time)

@app.route('/add', methods=['POST'])
def add_item():
    data = load_data()
    new_item = {
        'string': request.json.get('string'),
        'lifespan': request.json.get('lifespan'),
        'last_refreshed': datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
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
        data[item_index]['last_refreshed'] = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        save_data(data)
        return jsonify({'success': True, 'item': data[item_index]})
    return jsonify({'success': False}), 400

@app.route('/delete/<int:item_index>', methods=['POST'])
def delete_item(item_index):
    data = load_data()
    if 0 <= item_index < len(data):
        del data[item_index]
        save_data(data)
        return jsonify({'success': True})
    return jsonify({'success': False}), 400

@app.route('/edit')
def edit():
    items = load_data()
    app_version = os.getenv('APP_VERSION', 'Unknown')
    return render_template('edit.html', items=items, app_version=app_version)

@app.route('/save', methods=['POST'])
def save_changes():
    updated_items = request.json.get('items', [])
    save_data(updated_items)
    return jsonify({'success': True})

@app.route('/version')
def get_version():
    try:
        version = check_output(['git', 'describe', '--tags']).strip().decode('utf-8')
        return version
    except Exception as e:
        return "Unknown Version"

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5555)