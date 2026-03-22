from fastapi import FastAPI
from app.routers.currencies import router as currencies_router
from app.routers.analysis import router as analysis_router

app = FastAPI(title="System do analizy kursów walut",
              description="test",
              version="1.0")

app.include_router(currencies_router)
app.include_router(analysis_router)

@app.get("/")
def test():
    return {"message": "API test magisterki"}

