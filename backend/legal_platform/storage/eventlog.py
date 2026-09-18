"""Append-only operational audit events. Never store credentials or document text."""
from __future__ import annotations
import json
from uuid import uuid4
from legal_platform.contracts.common import now_utc, utc_iso


def init_audit_log(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS audit_log (
        id TEXT PRIMARY KEY, timestamp TEXT NOT NULL, service TEXT NOT NULL,
        module TEXT NOT NULL, event TEXT NOT NULL, entity_type TEXT,
        entity_id TEXT, severity TEXT NOT NULL, message TEXT, metadata TEXT
    )''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_log(entity_id, timestamp)')
    conn.commit()


def log_event(conn, *, service, module, event, entity_type=None, entity_id=None,
              severity='INFO', message='', metadata=None, **extra):
    event_id = str(uuid4())
    conn.execute('INSERT INTO audit_log VALUES (?,?,?,?,?,?,?,?,?,?)', (
        event_id, utc_iso(now_utc()), service, module, event, entity_type,
        str(entity_id) if entity_id is not None else None, severity, message,
        json.dumps(metadata or {}, default=str, ensure_ascii=False)))
    conn.commit()
    return event_id


def recent_events(conn, *, entity_id=None, service=None, event=None, limit=100, **filters):
    clauses, values = [], []
    for key, value in [('entity_id', entity_id), ('service', service), ('event', event)]:
        if value is not None:
            clauses.append(key + ' = ?')
            values.append(str(value))
    where = ' WHERE ' + ' AND '.join(clauses) if clauses else ''
    rows = conn.execute('SELECT * FROM audit_log' + where + ' ORDER BY timestamp DESC, rowid DESC LIMIT ?',
                        (*values, max(1, min(int(limit), 1000))))
    result = []
    for row in rows:
        item = dict(row)
        item['metadata'] = json.loads(item['metadata'] or '{}')
        result.append(item)
    return result
