"""
Database Service - SQLite database for tracking videos, exports, and templates
Completely local, no external database needed
"""

import sqlite3
import os
import json
from datetime import datetime
from typing import Optional, List, Dict
from pathlib import Path


DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database.db")


def get_connection() -> sqlite3.Connection:
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """Initialize database tables"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS exports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_name TEXT NOT NULL,
            story_text TEXT NOT NULL,
            hook_text TEXT,
            template_name TEXT DEFAULT 'Classic',
            niche TEXT DEFAULT 'general',
            duration REAL DEFAULT 0,
            output_path TEXT,
            uid TEXT DEFAULT '',
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            file_size INTEGER DEFAULT 0
        );
        
        CREATE TABLE IF NOT EXISTS templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            config TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_exports_status 
            ON exports(status);
        CREATE INDEX IF NOT EXISTS idx_exports_created 
            ON exports(created_at);
    """)
    
    conn.commit()
    conn.close()
    print(f"[OK] Database initialized: {DB_PATH}")


def save_export(
    video_name: str,
    story_text: str,
    hook_text: Optional[str] = None,
    template_name: str = "Classic",
    niche: str = "general",
    output_path: Optional[str] = None,
    duration: float = 0,
    file_size: int = 0,
    uid: str = "",
) -> int:
    """Save an export record to database"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO exports 
            (video_name, story_text, hook_text, template_name, niche, 
             output_path, duration, file_size, status, uid)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'completed', ?)
    """, (video_name, story_text, hook_text, template_name, niche,
          output_path, duration, file_size, uid))
    
    export_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return export_id


def get_exports(limit: int = 20, offset: int = 0) -> List[Dict]:
    """Get recent exports"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM exports 
        ORDER BY created_at DESC 
        LIMIT ? OFFSET ?
    """, (limit, offset))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]


def get_export(export_id: int) -> Optional[Dict]:
    """Get a single export by ID"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM exports WHERE id = ?", (export_id,))
    row = cursor.fetchone()
    conn.close()
    
    return dict(row) if row else None


def update_export_status(export_id: int, status: str):
    """Update export status"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        "UPDATE exports SET status = ? WHERE id = ?",
        (status, export_id)
    )
    
    conn.commit()
    conn.close()


def get_statistics() -> Dict:
    """Get dashboard statistics"""
    conn = get_connection()
    cursor = conn.cursor()
    
    stats = {}
    
    cursor.execute("SELECT COUNT(*) as total FROM exports")
    stats["total_exports"] = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM exports WHERE status = 'completed'")
    stats["completed_exports"] = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT niche, COUNT(*) as count 
        FROM exports 
        GROUP BY niche 
        ORDER BY count DESC 
        LIMIT 5
    """)
    stats["top_niches"] = [dict(row) for row in cursor.fetchall()]
    
    cursor.execute("""
        SELECT DATE(created_at) as date, COUNT(*) as count 
        FROM exports 
        GROUP BY DATE(created_at) 
        ORDER BY date DESC 
        LIMIT 7
    """)
    stats["daily_counts"] = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    return stats


# Initialize database on import
init_db()
