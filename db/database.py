"""SQLite database module for logging elevator records."""
import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "elevator_data.db")

class ElevatorDB:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self._create_table()

    def _create_table(self):
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                measured_weight REAL,
                load_limit REAL,
                object_count INTEGER DEFAULT 0,
                detected_objects TEXT DEFAULT '',
                human_detected INTEGER DEFAULT 0,
                alert_type TEXT DEFAULT 'SAFE',
                status TEXT DEFAULT 'Normal',
                data_source TEXT DEFAULT 'Simulation'
            )
        ''')
        self.conn.commit()

    def save_record(self, weight, limit, obj_count, objects, human, alert, status, source):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.conn.execute('''
            INSERT INTO records 
            (timestamp, measured_weight, load_limit, object_count, detected_objects,
             human_detected, alert_type, status, data_source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (ts, weight, limit, obj_count, objects, 1 if human else 0, alert, status, source))
        self.conn.commit()
        return ts

    def get_records(self, limit=100):
        cursor = self.conn.execute(
            'SELECT timestamp, measured_weight, alert_type, data_source FROM records ORDER BY id DESC LIMIT ?',
            (limit,)
        )
        return cursor.fetchall()

    def get_record_count(self):
        cursor = self.conn.execute('SELECT COUNT(*) FROM records')
        return cursor.fetchone()[0]

    def clear_all(self):
        self.conn.execute('DELETE FROM records')
        self.conn.commit()

    def close(self):
        self.conn.close()
