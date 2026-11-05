from flask import Flask, render_template, request, jsonify
import json
import re
from datetime import datetime, timedelta
from subprocess import check_output
import os
import uuid
from typing import Dict, List

import clock
import stats

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.jinja_env.auto_reload = True

# Custom Jinja2 filter to convert string to datetime
@app.template_filter('to_datetime')
def to_datetime(value):
    return datetime.strptime(value, '%Y-%m-%dT%H:%M:%S')

DATA_FILE = 'data/data.json'
HISTORY_FILE = 'data/refresh_history.json'
COMPLETIONS_FILE = 'data/completions.json'
CALENDAR_DAYS = 30

TIME_FORMAT = '%Y-%m-%dT%H:%M:%S'

def _ensure_ids(data):
    """Give every task a stable id. Returns True if any id was added."""
    changed = False
    for item in data:
        if not item.get('id'):
            item['id'] = uuid.uuid4().hex[:8]
            changed = True
    return changed

def load_data():
    try:
        with open(DATA_FILE, 'r') as file:
            data = json.load(file)
    except FileNotFoundError:
        return []
    if _ensure_ids(data) | _ensure_tracking(data):
        save_data(data)
    return data

def save_data(data):
    _ensure_ids(data)
    _ensure_tracking(data)
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, 'w') as file:
        json.dump(data, file, indent=4)

def load_events() -> List[dict]:
    try:
        with open(COMPLETIONS_FILE, 'r') as file:
            events = json.load(file)
            return events if isinstance(events, list) else []
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def _write_events(events: List[dict]):
    """Atomic write so a crash can never leave a half-written log."""
    os.makedirs(os.path.dirname(COMPLETIONS_FILE), exist_ok=True)
    tmp = COMPLETIONS_FILE + '.tmp'
    with open(tmp, 'w') as file:
        json.dump(events, file, indent=1)
    os.replace(tmp, COMPLETIONS_FILE)

def log_event(task_id, kind, done_at, on_time=None, at=None):
    """Append to the completion log. kind: baseline | done | edit."""
    events = load_events()
    events.append({
        'task_id': task_id,
        'kind': kind,
        'at': (at or clock.now()).strftime(TIME_FORMAT),
        'done_at': done_at,
        'on_time': on_time,
    })
    _write_events(events)

def _ensure_tracking(data):
    """Give every task `created` + `icon`, and a baseline log event when it
    starts being tracked (history starts from that moment, not before)."""
    changed = False
    for item in data:
        if 'icon' not in item:
            item['icon'] = None
            changed = True
        if not item.get('created'):
            now = clock.now()
            item['created'] = now.strftime(TIME_FORMAT)
            log_event(item['id'], 'baseline', item['last_refreshed'], at=now)
            changed = True
    return changed

def task_age_days(item, now=None):
    now = now or clock.now()
    return (now - datetime.strptime(item['last_refreshed'], TIME_FORMAT)).total_seconds() / 86400

def task_status(item, now=None):
    """green: under half of lifespan, yellow: half or more, red: expired."""
    return stats.status_from_age(task_age_days(item, now), item['lifespan'])

app.jinja_env.globals['task_status'] = task_status

def mark_refreshed(data, index):
    """Refresh the task at `index`, update history, return the item."""
    now = clock.now()
    was_red = task_status(data[index], now) == 'red'
    data[index]['last_refreshed'] = now.strftime(TIME_FORMAT)
    save_data(data)
    log_event(data[index]['id'], 'done', data[index]['last_refreshed'], on_time=not was_red, at=now)
    history = load_history()
    today_key = now.date().isoformat()
    history[today_key] = history.get(today_key, 0) + 1
    save_history(history)
    return data[index]

def _build_history_from_items(items: List[dict], days: int = CALENDAR_DAYS) -> Dict[str, int]:
    history: Dict[str, int] = {}
    if not items:
        return history

    cutoff_date = (clock.now() - timedelta(days=days - 1)).date()
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
    today = clock.now().date()
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
    current_time = clock.now()
    history = sync_history_with_items(load_history(), items)
    save_history(history)
    calendar_data = build_calendar_data(history)
    total_tasks = len(items)
    return render_template(
        'index.html',
        items=items,
        current_time=current_time,
        calendar_data=calendar_data,
        total_tasks=total_tasks
    )

ICON_PATTERN = re.compile(r'^[a-z0-9_]+$')

def _valid_lifespan(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0

def _parse_last_done(value, current):
    """Accept 'YYYY-MM-DD' (keeps the old time of day) or a full timestamp.
    Returns the normalised string, or None if invalid / in the future."""
    try:
        if len(value) == 10:
            keep_time = datetime.strptime(current, TIME_FORMAT).time()
            parsed = datetime.combine(datetime.strptime(value, '%Y-%m-%d').date(), keep_time)
        else:
            parsed = datetime.strptime(value, TIME_FORMAT)
    except (TypeError, ValueError):
        return None
    if parsed > clock.now():
        return None
    return parsed.strftime(TIME_FORMAT)

@app.route('/add', methods=['POST'])
def add_item():
    data = load_data()
    now = clock.now()
    payload = request.get_json(silent=True) or {}
    name = str(payload.get('string') or '').strip()
    lifespan = payload.get('lifespan')
    new_item = {
        'string': name,
        'lifespan': lifespan,
        'last_refreshed': now.strftime('%Y-%m-%dT%H:%M:%S'),
        'icon': payload.get('icon')
    }
    if name and _valid_lifespan(lifespan):
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
        return jsonify({'success': True, 'item': mark_refreshed(data, item_index)})
    return jsonify({'success': False}), 400

@app.route('/api/tasks')
def api_tasks():
    now = clock.now()
    tasks = []
    items = load_data()
    metrics = {m['id']: m for m in stats.compute_stats(items, load_events(), 'all', now)['tasks']}
    for item in items:
        tasks.append({
            'id': item['id'],
            'string': item['string'],
            'lifespan': item['lifespan'],
            'last_refreshed': item['last_refreshed'],
            'age_days': round(task_age_days(item, now), 2),
            'status': task_status(item, now),
            'icon': item.get('icon'),
            'on_time_pct': metrics[item['id']]['on_time_pct'],
            'strip': metrics[item['id']]['strip'],
        })
    return jsonify(tasks)

@app.route('/api/stats')
def api_stats():
    range_key = request.args.get('range', '30')
    if range_key not in stats.RANGES:
        return jsonify({'error': 'range must be 30, 90 or all'}), 400
    return jsonify(stats.compute_stats(load_data(), load_events(), range_key))

@app.route('/api/tasks/<task_id>/refresh', methods=['POST'])
def api_refresh_task(task_id):
    data = load_data()
    for index, item in enumerate(data):
        if item['id'] == task_id:
            mark_refreshed(data, index)
            return jsonify({'success': True, 'id': task_id, 'string': item['string']})
    return jsonify({'success': False, 'error': 'not found'}), 404

@app.route('/api/tasks/<task_id>', methods=['PATCH'])
def api_update_task(task_id):
    """Edit name / frequency / last-done date / icon of one task."""
    payload = request.get_json(silent=True) or {}
    data = load_data()
    item = next((t for t in data if t['id'] == task_id), None)
    if item is None:
        return jsonify({'success': False, 'error': 'not found'}), 404

    if 'string' in payload:
        name = str(payload['string'] or '').strip()
        if not name:
            return jsonify({'success': False, 'error': 'name is required'}), 400
        item['string'] = name
    if 'lifespan' in payload:
        if not _valid_lifespan(payload['lifespan']):
            return jsonify({'success': False, 'error': 'frequency must be a positive number'}), 400
        item['lifespan'] = payload['lifespan']
    if 'icon' in payload:
        icon = payload['icon']
        if icon is not None and not (isinstance(icon, str) and ICON_PATTERN.match(icon)):
            return jsonify({'success': False, 'error': 'invalid icon'}), 400
        item['icon'] = icon
    edited_last_done = None
    if 'last_refreshed' in payload:
        parsed = _parse_last_done(payload['last_refreshed'], item['last_refreshed'])
        if parsed is None:
            return jsonify({'success': False, 'error': 'invalid or future date'}), 400
        if parsed != item['last_refreshed']:
            item['last_refreshed'] = edited_last_done = parsed

    save_data(data)
    if edited_last_done:
        log_event(task_id, 'edit', edited_last_done)
    return jsonify({'success': True, 'item': item})

@app.route('/api/tasks/<task_id>', methods=['DELETE'])
def api_delete_task(task_id):
    data = load_data()
    remaining = [t for t in data if t['id'] != task_id]
    if len(remaining) == len(data):
        return jsonify({'success': False, 'error': 'not found'}), 404
    save_data(remaining)
    return jsonify({'success': True})

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
    existing = {item['id']: item for item in load_data()}
    for item in updated_items:
        old = existing.get(item.get('id'))
        if old:
            # the edit page only sends some fields: keep created/icon/etc.
            for key, value in old.items():
                item.setdefault(key, value)
            if item.get('last_refreshed') != old['last_refreshed']:
                log_event(old['id'], 'edit', item['last_refreshed'])
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
