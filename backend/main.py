import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (admin, auth, barcodes, builds, catalog, chat, market, notifications, reference, reservations, seller,
                     stock)
from app.core.config import settings
from app.db.database import SessionLocal, init_db
from app.services.importer import fail_stale_imports


async def expire_reservations_hourly() -> None:
    """Phase 11: reservations whose term has passed become "expired" (the lists also check it when opened)."""
    from app.services.notifications import purge
    from app.services.reservations import expire_due, remind_expiring

    while True:
        with suppress(Exception), SessionLocal() as db:
            expire_due(db)
            remind_expiring(db)  # phase 12.5: "бронь истекает сегодня" to the buyer
            purge(db)  # notifications older than 30 days
        await asyncio.sleep(3600)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    fail_stale_imports()
    task = asyncio.create_task(expire_reservations_hourly())
    yield
    task.cancel()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    # Local-only app: Vite may move to 5174+ when 5173 is busy
    allow_origin_regex=r"http://localhost:\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(seller.router, prefix="/api")
app.include_router(reference.router, prefix="/api")
app.include_router(catalog.router, prefix="/api")
app.include_router(market.router, prefix="/api")
app.include_router(builds.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(reservations.router, prefix="/api")
app.include_router(stock.router, prefix="/api")
app.include_router(barcodes.router, prefix="/api")
app.include_router(notifications.router, prefix="/api")
app.include_router(admin.public, prefix="/api")
app.include_router(admin.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok"}
