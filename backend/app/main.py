from fastapi import FastAPI
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from app.routers import products, orders, invoices, auth, users, roles, stock, reports
import os
from app.database import engine
from app import models

from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.database import SessionLocal
from app.security import cleanup_blacklist

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "..", "frontend")

# ✅ THÊM MỚI: scheduler setup
scheduler = AsyncIOScheduler()

def scheduled_cleanup():
    db = SessionLocal()
    try:
        cleanup_blacklist(db)
    finally:
        db.close()

# ✅ THÊM MỚI: lifespan thay vì để app chạy trơn
@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(scheduled_cleanup, "interval", hours=1)
    scheduler.start()
    yield
    scheduler.shutdown()

app = FastAPI(  
                lifespan=lifespan,
                # docs_url=None,
                # redoc_url=None,
                title="🔥 ĐẶC SẢN QUÊ HƯƠNG 🔥"
                )

models.Base.metadata.create_all(bind=engine)


# frontend static (css, js, images)
app.mount(
    "/static",StaticFiles(directory=os.path.join(FRONTEND_DIR, "static")),name="static")


# Ảnh upload sản phẩm
app.mount(
    "/uploads",StaticFiles(directory="app/static/uploads"),name="uploads")
# API routers
app.include_router(auth.router, prefix="/api")
app.include_router(products.router, prefix="/api")
app.include_router(roles.router, prefix="/api")
app.include_router(users.router, prefix="/api") 
app.include_router(orders.router, prefix="/api")
app.include_router(invoices.router, prefix="/api")
app.include_router(stock.router, prefix="/api")
app.include_router(reports.router, prefix="/api")


@app.get("/favicon.ico")
def favicon():
    path = os.path.join(FRONTEND_DIR, "static", "images", "favicon.ico")
    if os.path.exists(path):
        return FileResponse(path)
    return {"error": "favicon not found"}

@app.get("/")
def home():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

@app.get("/{page_name}")
def serve_page(page_name: str):
    # file_path = os.path.join(FRONTEND_DIR, f"{page_name}")
    file_path = os.path.realpath(os.path.join(FRONTEND_DIR, page_name))
    # Chặn path traversal (../../etc/passwd)
    if not file_path.startswith(os.path.realpath(FRONTEND_DIR)):
        return JSONResponse(status_code=403, content={"error": "Forbidden"})
    
    if os.path.exists(file_path):
        return FileResponse(file_path)
    return JSONResponse(
        status_code=404,
        content={"error": "Page not found"}
    )

