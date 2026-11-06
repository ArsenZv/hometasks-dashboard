"""Pure statistics helpers: no Flask, no file access.

Everything is derived from two inputs:
  * tasks:  [{id, string, lifespan, last_refreshed, created, icon}, ...]
  * events: [{task_id, at, done_at, kind, on_time}, ...]   (data/completions.json)

Event kinds:
  baseline - written when a task starts being tracked (done_at = its last refresh then)
  done     - the task was completed (counts as a completion; on_time says if it was not red)
  edit     - last-done date was corrected by hand (not a completion)

A task's colour on any past day is reconstructed from the latest event recorded
up to the end of that day, so no daily snapshot job is needed. Days before a
task's `created` date are "unknown" (None).
"""
from collections import defaultdict
from datetime import datetime, timedelta

import clock

TIME_FORMAT = '%Y-%m-%dT%H:%M:%S'
STRIP_DAYS = 10
RANGES = {'30': 30, '90': 90, 'all': None}


def parse(ts):
    return datetime.strptime(ts, TIME_FORMAT)


def status_from_age(age_days, lifespan):
    """green: under half of lifespan, yellow: half or more, red: expired."""
    if 0 <= age_days < lifespan / 2:
        return 'green'
    if lifespan / 2 <= age_days < lifespan:
        return 'yellow'
    return 'red'


def group_events(events):
    by_task = defaultdict(list)
    for ev in events:
        by_task[ev['task_id']].append(ev)
    for evs in by_task.values():
        evs.sort(key=lambda e: e['at'])
    return by_task


def status_at(task, task_events, ref):
    """Colour of `task` as seen at datetime `ref`, or None if untracked then."""
    seen = [e for e in task_events if parse(e['at']) <= ref]
    if not seen:
        return None
    age = (ref - parse(seen[-1]['done_at'])).total_seconds() / 86400
    return status_from_age(age, task['lifespan'])


def status_on_day(task, task_events, day, now):
    end = datetime.combine(day, datetime.max.time()).replace(microsecond=0)
    return status_at(task, task_events, min(end, now))


def created_date(task, now):
    try:
        return parse(task['created']).date()
    except (KeyError, ValueError):
        return now.date()


def task_metrics(task, task_events, now, window_start):
    """Per-task numbers for the window [window_start, today]."""
    today = now.date()
    done = [e for e in task_events if e['kind'] == 'done'
            and parse(e['at']).date() >= window_start]
    on_time = sum(1 for e in done if e.get('on_time'))

    strip = []
    for offset in range(STRIP_DAYS - 1, -1, -1):
        day = today - timedelta(days=offset)
        strip.append({'date': day.isoformat(), 'status': status_on_day(task, task_events, day, now)})

    start = max(window_start, created_date(task, now))
    days = max((today - start).days + 1, 1)
    expected = max(days / task['lifespan'], 1.0)   # at least one expected completion
    age = (now - parse(task['last_refreshed'])).total_seconds() / 86400
    return {
        'id': task['id'],
        'string': task['string'],
        'status': status_from_age(age, task['lifespan']),
        'age_days': round(age, 2),
        'icon': task.get('icon'),
        'emoji': task.get('emoji'),
        'lifespan': task['lifespan'],
        'completions': len(done),
        'on_time_pct': round(100 * on_time / len(done)) if done else None,
        'last_done': task['last_refreshed'],
        'strip': strip,
        # completions relative to how many were due: 1.0 = done exactly when due
        'ease': round(len(done) / expected, 2),
    }


def procrastination(tasks, by_task, window_start, now):
    """Streaks of consecutive days on which >= 50% of tasks were red."""
    today = now.date()
    streaks, run_start, run_len = [], None, 0
    day = window_start
    while day <= today:
        known = [status_on_day(t, by_task.get(t['id'], []), day, now) for t in tasks]
        known = [s for s in known if s]
        lazy = bool(known) and known.count('red') / len(known) >= 0.5
        if lazy:
            run_start = run_start or day
            run_len += 1
        elif run_len:
            streaks.append({'start': run_start.isoformat(), 'length': run_len})
            run_start, run_len = None, 0
        day += timedelta(days=1)
    current = run_len
    if run_len:
        streaks.append({'start': run_start.isoformat(), 'length': run_len})

    histogram = defaultdict(int)
    for s in streaks:
        histogram[s['length']] += 1
    return {
        'longest': max((s['length'] for s in streaks), default=0),
        'current': current,
        'streaks': streaks,
        'histogram': [{'length': k, 'count': histogram[k]} for k in sorted(histogram)],
    }


def compute_stats(tasks, events, range_key='30', now=None):
    now = now or clock.now()
    today = now.date()
    by_task = group_events(events)
    days = RANGES.get(range_key, 30)

    tracking_start = min((created_date(t, now) for t in tasks), default=today)
    window_start = today - timedelta(days=days - 1) if days else tracking_start
    window_start = max(window_start, tracking_start)

    # current snapshot
    current = {}
    for t in tasks:
        age = (now - parse(t['last_refreshed'])).total_seconds() / 86400
        current[t['id']] = {'status': status_from_age(age, t['lifespan']), 'age': age}
    distribution = {c: sum(1 for v in current.values() if v['status'] == c)
                    for c in ('green', 'yellow', 'red')}

    # share of task-days per colour across the window
    counts = {'green': 0, 'yellow': 0, 'red': 0}
    day = window_start
    while day <= today:
        for t in tasks:
            s = status_on_day(t, by_task.get(t['id'], []), day, now)
            if s:
                counts[s] += 1
        day += timedelta(days=1)
    total = sum(counts.values())
    progress = {c: (round(100 * n / total, 1) if total else 0) for c, n in counts.items()}

    per_task = [task_metrics(t, by_task.get(t['id'], []), now, window_start) for t in tasks]
    ranked = sorted(per_task, key=lambda m: m['ease'])

    oldest = sorted(tasks, key=lambda t: current[t['id']]['age'], reverse=True)[:3]

    # suggestions: the yellow task closest to turning red, and the most overdue red one
    yellow = sorted((t for t in tasks if current[t['id']]['status'] == 'yellow'),
                    key=lambda t: t['lifespan'] - current[t['id']]['age'])[:1]
    red = sorted((t for t in tasks if current[t['id']]['status'] == 'red'),
                 key=lambda t: current[t['id']]['age'] - t['lifespan'], reverse=True)[:1]

    def brief(t, **extra):
        return {'id': t['id'], 'string': t['string'], 'icon': t.get('icon'), 'emoji': t.get('emoji'),
                'status': current[t['id']]['status'],
                'age_days': round(current[t['id']]['age'], 1), **extra}

    return {
        'range': range_key if range_key in RANGES else '30',
        'window_start': window_start.isoformat(),
        'window_days': (today - window_start).days + 1,
        'distribution': distribution,
        'progress': progress,
        'oldest': [brief(t) for t in oldest],
        'easiest': ranked[::-1][:3] if per_task else [],
        'hated': ranked[:3],
        'procrastination': procrastination(tasks, by_task, window_start, now),
        'suggestions': {
            'before_red': [brief(t, days_left=round(t['lifespan'] - current[t['id']]['age'], 1)) for t in yellow],
            'overdue': [brief(t, days_overdue=round(current[t['id']]['age'] - t['lifespan'], 1)) for t in red],
        },
        'tasks': per_task,
    }
