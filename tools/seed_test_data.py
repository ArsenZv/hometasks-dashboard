"""Generate RANDOM test data for local development. Never run this on the NAS.

Writes data/data.json, data/completions.json and data/refresh_history.json with
~120 days of fake history for the real task list, with a few "lazy weeks".
Any existing data files are first copied to data/backup-before-seed/.
Usage: python tools/seed_test_data.py [--days 120] [--seed 1]
"""
import argparse, json, random, shutil, sys, uuid
from datetime import datetime, timedelta
from pathlib import Path

FMT = '%Y-%m-%dT%H:%M:%S'
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import clock  # noqa: E402  (Paris time, same as the app)

DATA = ROOT / 'data'

# (name, icon, lifespan days, diligence 0..1 = how soon after due it gets done)
TASKS = [
    ('Water flowers', 'water_flowers', 3, 0.8),
    ('Prepare food', 'prepare_food', 1, 0.9),
    ('Washing machine', 'wash_clothes', 4, 0.7),
    ('Dry clothes', 'dry_clothes', 3, 0.6),
    ('Wash the car', 'wash_car', 21, 0.3),
    ('Запусти пилосос', 'vacuum', 4, 0.5),
    ('Помий посуд', 'dishes', 1, 0.9),
    ('Поприбирай у спальні і вітальні', 'room_cleaning', 7, 0.5),
    ('Поприбирай у ванні', 'bathroom_cleaning', 7, 0.4),
    ('Поприбирай у кухні', 'kitchen_cleaning', 5, 0.6),
    ('Купи їсти собаці', 'dog_food', 14, 0.7),
    ('Розчеси собаку', 'brush_dog', 5, 0.35),
    ('Поприбирай на терасі', 'terrace_cleaning', 14, 0.2),
]

ap = argparse.ArgumentParser()
ap.add_argument('--days', type=int, default=120)
ap.add_argument('--seed', type=int, default=1)
args = ap.parse_args()
rnd = random.Random(args.seed)

DATA.mkdir(exist_ok=True)
existing = [p for p in DATA.glob('*.json')]
if existing:
    backup = DATA / 'backup-before-seed'
    backup.mkdir(exist_ok=True)
    for p in existing:
        shutil.copy2(p, backup / p.name)

now = clock.now().replace(microsecond=0)
start = now - timedelta(days=args.days)
lazy = [(start + timedelta(days=rnd.randint(10, args.days - 8))) for _ in range(3)]
lazy = [(d, d + timedelta(days=rnd.randint(3, 7))) for d in lazy]
is_lazy = lambda t: any(a <= t <= b for a, b in lazy)

tasks, events, history = [], [], {}
for name, icon, lifespan, diligence in TASKS:
    tid = uuid.uuid4().hex[:8]
    last = start + timedelta(hours=rnd.randint(0, 20))
    events.append({'task_id': tid, 'kind': 'baseline', 'at': start.strftime(FMT),
                   'done_at': last.strftime(FMT), 'on_time': None})
    t = last
    while True:
        # next completion: before due when diligent, late when not
        wait = lifespan * (0.45 + (1 - diligence) * rnd.uniform(0.3, 1.8) + rnd.uniform(0, 0.3))
        t = t + timedelta(days=wait)
        while is_lazy(t):
            t += timedelta(days=1)
        t = t.replace(hour=rnd.randint(7, 22), minute=rnd.randint(0, 59), second=0)
        if t > now:
            break
        age = (t - last).total_seconds() / 86400
        events.append({'task_id': tid, 'kind': 'done', 'at': t.strftime(FMT),
                       'done_at': t.strftime(FMT), 'on_time': age < lifespan})
        history[t.date().isoformat()] = history.get(t.date().isoformat(), 0) + 1
        last = t
    tasks.append({'string': name, 'lifespan': lifespan, 'last_refreshed': last.strftime(FMT),
                  'id': tid, 'icon': icon, 'created': start.strftime(FMT)})

events.sort(key=lambda e: e['at'])
(DATA / 'data.json').write_text(json.dumps(tasks, indent=4, ensure_ascii=False))
(DATA / 'completions.json').write_text(json.dumps(events, indent=1, ensure_ascii=False))
(DATA / 'refresh_history.json').write_text(json.dumps(history, indent=4))
print(f'{len(tasks)} tasks, {len(events)} events, lazy periods: ' +
      ', '.join(f'{a:%m-%d}..{b:%m-%d}' for a, b in lazy))
