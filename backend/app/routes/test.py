from fastapi import APIRouter
from app.db.mongodb import db

router = APIRouter()

@router.get("/db-test")
async def db_test():
    collections = await db.list_collection_names()
    return {"collections": collections}
