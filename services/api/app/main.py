from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.domains.analytics.incidents.router import router as incidents_router
from app.domains.procurement.suppliers.router import router as suppliers_router

app = FastAPI(
    title="Brasaland API",
    description="Internal API for incident analysis and supplier directory management.",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3002",
        "http://127.0.0.1:3002",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(incidents_router)
app.include_router(suppliers_router)


@app.get("/health", tags=["health"])
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}