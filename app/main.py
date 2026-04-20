from fastapi import FastAPI
from app.routers.currencies import router as currencies_router
from app.routers.analysis import router as analysis_router

app = FastAPI(title="NBP Currency Analysis App",
              description="API to analyse influence of world events",
              version="1.0")

app.include_router(currencies_router)
app.include_router(analysis_router)

@app.get("/")
def test():
    return {"name": "NBP Currency Analysis App"}

