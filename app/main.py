from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api import routes_input, routes_config, routes_kalkulasi, routes_export

app = FastAPI(
    title="Sistem Skoring Risiko-Return Emiten BEI",
    description="API untuk analisis risiko-return emiten BEI 2020-2025",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_input.router,     prefix=settings.API_PREFIX)
app.include_router(routes_config.router,    prefix=settings.API_PREFIX)
app.include_router(routes_kalkulasi.router, prefix=settings.API_PREFIX)
app.include_router(routes_export.router,    prefix=settings.API_PREFIX)

@app.get("/")
def root():
    return {"status": "ok", "message": "Sistem Skoring BEI API berjalan"}

@app.get("/health")
def health():
    return {"status": "healthy"}
