from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db.mongodb import connect_db, close_db
from app.routes import test, auth


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        'http://localhost:5173',  # Vite frontend
        "http://127.0.0.1:5173",
        "http://localhost:8000",  # FastAPI docs
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    
)


@app.on_event("startup")
async def startup():
    await connect_db()

@app.on_event("shutdown")
async def shutdown():
    await close_db()

app.include_router(test.router, prefix="/api")
app.include_router(auth.router)



@app.get("/")
def root():
    return {"status": "Backend running"}
