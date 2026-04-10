from fastapi import FastAPI
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from app.routers import products, orders, invoices, auth
import os
from app.database import engine
from app import models


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "..", "frontend")

app = FastAPI(title="🔥 ĐẶC SẢN QUÊ HƯƠNG 🔥")

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
app.include_router(orders.router, prefix="/api")
app.include_router(invoices.router, prefix="/api")


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
    file_path = os.path.join(FRONTEND_DIR, f"{page_name}")
    if os.path.exists(file_path):
        return FileResponse(file_path)
    return JSONResponse(
        status_code=404,
        content={"error": "Page not found"}
    )

