# backend/worker.py - Background job processor
import asyncio
import os
import sys
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.jobstores.redis import RedisJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor
from sqlalchemy import create_engine
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up database and session imports from main for context
# We must ensure main.py is in the path or use relative imports carefully.
try:
    from main import SessionLocal, Website, DATABASE_URL
    # Import the engine from audit_engine to avoid circular dependency with Base
    from audit_engine import SEOAuditEngine 
except ImportError as e:
    print(f"Error importing dependencies in worker.py: {e}")
    # In a production environment, this should log and retry
    sys.exit(1)


# --- Scheduler Setup ---
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
# Use the main database URL for job store for persistence
JOB_STORE_URL = DATABASE_URL.replace("postgresql://", "sqlite:///jobs.sqlite") # sqlite is easier for the worker only

jobstores = {
    'default': SQLAlchemyJobStore(url=DATABASE_URL)
}
# Use AsyncIOExecutor for non-blocking execution of the job function
executors = {
    'default': AsyncIOExecutor()
}
job_defaults = {
    'coalesce': True,
    'max_instances': 1
}

scheduler = AsyncIOScheduler(
    jobstores=jobstores, 
    executors=executors, 
    job_defaults=job_defaults
)


async def run_daily_audits():
    """Run daily audits for all active websites"""
    db = SessionLocal()
    # Only audit active websites
    websites = db.query(Website).filter(Website.is_active == True).all() 
    
    print(f"Worker: Found {len(websites)} websites for daily audit.")
    
    # We will run audits sequentially to avoid overwhelming resources and APIs
    for website in websites:
        try:
            print(f"Worker: Starting audit for {website.domain} (ID: {website.id})")
            engine = SEOAuditEngine(website.id)
            # The run_comprehensive_audit method is now synchronous using __enter__/__exit__
            # but we run it inside an async worker function. If it were fully async, 
            # we'd use await. For this setup, we run it directly.
            results = await engine.run_comprehensive_audit() # It has an async wrapper
            
            # The commit/update logic is inside the audit engine now.
            print(f"Worker: Audit completed for {website.domain}: Score {results['health_score']}")
            
        except Exception as e:
            print(f"Worker: Error auditing {website.domain}: {e}")
            
    db.close()
    print("Worker: Daily audit batch completed.")


async def main():
    print("Worker: Starting APScheduler...")
    
    # Add a job if it doesn't exist
    if not scheduler.get_job('daily_audits'):
        # Schedule daily audits at 2 AM
        scheduler.add_job(
            run_daily_audits,
            'cron',
            hour=2, # 2 AM
            minute=0,
            id='daily_audits',
            replace_existing=True
        )
        print("Worker: Daily audit job scheduled for 2:00 AM.")
    
    scheduler.start()
    
    # Keep the worker running indefinitely
    try:
        print("Worker: Running until interrupted...")
        # A simple non-blocking way to keep the main thread alive
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        print("Worker: Shutting down scheduler.")
        scheduler.shutdown()

if __name__ == "__main__":
    try:
        # Initial database creation check - ensure tables exist for the job store
        from main import create_db 
        create_db()
        asyncio.run(main())
    except Exception as e:
        print(f"Worker failed to start: {e}")
