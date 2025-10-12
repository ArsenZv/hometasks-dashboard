from flask import Flask, render_template, request, jsonify
import json
from datetime import datetime, timedelta
from subprocess import check_output
import os
from typing import Dict, List

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.jinja_env.auto_reload = True

# Custom Jinja2 filter to convert string to datetime
@app.template_filter('to_datetime')
def to_datetime(value):
    return datetime.strptime(value, '%Y-%m-%dT%H:%M:%S')

DATA_FILE = 'data/data.json'
HISTORY_FILE = 'data/refresh_history.json'
CALENDAR_DAYS = 30

def load_data():
    try:
        with open(DATA_FILE, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return []

def save_data(data):
    with open(DATA_FILE, 'w') as file:
        json.dump(data, file, indent=4)

def _build_history_from_items(items: List[dict], days: int = CALENDAR_DAYS) -> Dict[str, int]:
    history: Dict[str, int] = {}
    if not items:
        return history

    cutoff_date = (datetime.now() - timedelta(days=days - 1)).date()
    for item in items:
        last_refreshed = item.get('last_refreshed')
        if not last_refreshed:
            continue
        try:
            refreshed_date = datetime.strptime(last_refreshed, '%Y-%m-%dT%H:%M:%S').date()
        except ValueError:
            continue
        if refreshed_date >= cutoff_date:
            day_key = refreshed_date.isoformat()
            history[day_key] = history.get(day_key, 0) + 1
    return history

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as file:
                data = json.load(file)
                if isinstance(data, dict):
                    return {str(k): int(v) for k, v in data.items()}
        except (json.JSONDecodeError, ValueError):
            pass

    history = _build_history_from_items(load_data())
    save_history(history)
    return history

def save_history(history: Dict[str, int]):
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    with open(HISTORY_FILE, 'w') as file:
        json.dump(history, file, indent=4)

def sync_history_with_items(history: Dict[str, int], items: List[dict]) -> Dict[str, int]:
    derived = _build_history_from_items(items)
    for day_key, count in derived.items():
        if history.get(day_key, 0) < count:
            history[day_key] = count
    return history

def build_calendar_data(history: Dict[str, int], days: int = CALENDAR_DAYS):
    today = datetime.now().date()
    start_date = today - timedelta(days=days - 1)
    calendar = []
    for offset in range(days):
        day = start_date + timedelta(days=offset)
        day_key = day.isoformat()
        calendar.append({
            'date': day_key,
            'count': history.get(day_key, 0)
        })
    return calendar

@app.route('/')
def index():
    items = load_data()
    current_time = datetime.now()
    history = sync_history_with_items(load_history(), items)
    save_history(history)
    calendar_data = build_calendar_data(history)
    return render_template(
        'index.html',
        items=items,
        current_time=current_time,
        calendar_data=calendar_data
    )

@app.route('/add', methods=['POST'])
def add_item():
    data = load_data()
    now = datetime.now()
    new_item = {
        'string': request.json.get('string'),
        'lifespan': request.json.get('lifespan'),
        'last_refreshed': now.strftime('%Y-%m-%dT%H:%M:%S')
    }
    if new_item['string'] and isinstance(new_item['lifespan'], (int, float)):
        data.append(new_item)
        save_data(data)
        history = sync_history_with_items(load_history(), data)
        save_history(history)
        return jsonify({'success': True, 'items': data})
    return jsonify({'success': False}), 400

@app.route('/refresh/<int:item_index>', methods=['POST'])
def refresh_item(item_index):
    data = load_data()
    if 0 <= item_index < len(data):
        now = datetime.now()
        data[item_index]['last_refreshed'] = now.strftime('%Y-%m-%dT%H:%M:%S')
        save_data(data)
        history = load_history()
        today_key = now.date().isoformat()
        history[today_key] = history.get(today_key, 0) + 1
        save_history(history)
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
    history = sync_history_with_items(load_history(), updated_items)
    save_history(history)
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
