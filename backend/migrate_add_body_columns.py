"""
Migration script to add body_text and body_html columns to email_analysis_logs table.
Run this once after deploying the updated code.

Usage:
    python migrate_add_body_columns.py
"""
import os
from dotenv import load_dotenv
import pymysql

load_dotenv()

DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "secret")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_NAME = os.getenv("DB_NAME", "email_phishing_agent")


def migrate():
    conn = pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
    )
    cursor = conn.cursor()

    # Check if columns already exist
    cursor.execute(
        "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
        "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'email_analysis_logs' "
        "AND COLUMN_NAME IN ('body_text', 'body_html')",
        (DB_NAME,)
    )
    existing = {row[0] for row in cursor.fetchall()}

    if 'body_text' not in existing:
        print("Adding 'body_text' column...")
        cursor.execute(
            "ALTER TABLE email_analysis_logs ADD COLUMN body_text TEXT NULL AFTER completion_tokens"
        )
        print("  ✓ body_text column added")
    else:
        print("  - body_text column already exists, skipping")

    if 'body_html' not in existing:
        print("Adding 'body_html' column...")
        cursor.execute(
            "ALTER TABLE email_analysis_logs ADD COLUMN body_html TEXT NULL AFTER body_text"
        )
        print("  ✓ body_html column added")
    else:
        print("  - body_html column already exists, skipping")

    conn.commit()
    cursor.close()
    conn.close()
    print("\nMigration completed successfully!")


if __name__ == "__main__":
    migrate()
