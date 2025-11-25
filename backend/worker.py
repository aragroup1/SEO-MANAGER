# backend/worker.py - Background job processor
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from audit_engine_enhanced import EnhancedSEOAuditEngine
from main import SessionLocal, Website

async def run_daily_audits():
    """Run daily audits for all websites"""
    db = SessionLocal()
    websites = db.query(Website).all()
    
    for website in websites:
        try:
            print(f"Running audit for {website.domain}")
            engine = EnhancedSEOAuditEngine(website.id)
            results = await engine.run_comprehensive_audit()
            print(f"Audit completed for {website.domain}: Score {results['health_score']}")
        except Exception as e:
            print(f"Error auditing {website.domain}: {e}")
    
    db.close()

async def main():
    scheduler = AsyncIOScheduler()
    
    # Schedule daily audits at 2 AM
    scheduler.add_job(
        run_daily_audits,
        'cron',
        hour=2,
        minute=0,
        id='daily_audits'
    )
    
    scheduler.start()
    
    # Keep the worker running
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        scheduler.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
