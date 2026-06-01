from fastapi import FastAPI
from app.routers.currencies import router as currencies_router
from app.routers.analysis import router as analysis_router
from app.services.nbp_api import init_http_client, close_http_client
from contextlib import asynccontextmanager
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logger.info("Loaded!")

@asynccontextmanager
async def lifespan(_app):
    await init_http_client()
    yield
    await close_http_client()


app = FastAPI(title="Currency Analysis App",
              description="API to analyse influence of world events",
              version="1.0",
              lifespan=lifespan)

app.include_router(currencies_router)
app.include_router(analysis_router)


@app.get("/")
def test():
    return {"name": "Connected successfully!"}