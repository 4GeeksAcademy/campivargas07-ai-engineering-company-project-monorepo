from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()  # Load .env file at startup

from app.domains.auth.router import router as auth_router
from app.domains.profiles.router import router as profiles_router
from app.domains.procurement.suppliers.router import router as suppliers_router
from app.domains.users.router import router as users_router

app = FastAPI(
    title="Brasaland API",
    description="Internal API for supplier directory management.",
    version="0.4.0",
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

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(profiles_router)
app.include_router(suppliers_router)


@app.get("/health", tags=["health"])
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}