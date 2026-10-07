from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import Base, engine
from app.routers import auth, projects, surveys


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Aereo Survey API",
    description="Backend for managing drone survey projects and their GeoJSON footprints.",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(surveys.router)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}
