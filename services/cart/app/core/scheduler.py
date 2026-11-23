from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.services.cart_cleanup import cleanup_expired_carts

scheduler = AsyncIOScheduler()


def start_scheduler():
    scheduler.add_job(
        cleanup_expired_carts,
        trigger="interval",
        hours=1,
        id="expired_cart_cleanup",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.start()


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)