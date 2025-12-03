# backend/migrate.py
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://seo_user:seo_password@localhost/seo_tool")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)

# Add missing columns to websites table
migration_sql = """
ALTER TABLE websites 
ADD COLUMN IF NOT EXISTS user_id INTEGER DEFAULT 1,
ADD COLUMN IF NOT EXISTS site_type VARCHAR DEFAULT 'custom',
ADD COLUMN IF NOT EXISTS shopify_store_url VARCHAR,
ADD COLUMN IF NOT EXISTS shopify_access_token VARCHAR,
ADD COLUMN IF NOT EXISTS monthly_traffic INTEGER;
"""

try:
    with engine.connect() as conn:
        conn.execute(text(migration_sql))
        conn.commit()
    print("Migration completed successfully!")
except Exception as e:
    print(f"Migration error: {e}")
