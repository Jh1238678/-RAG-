import asyncio
from app.api.routes_chat import chat
from app.models.schemas import ChatRequest
from app.db.session import SessionLocal

async def test():
    req = ChatRequest(question="What is AI?", session_id="test-session", document_ids=[])
    db = SessionLocal()
    try:
        res = await chat(req, db)
        print(res)
    except Exception as e:
        import traceback
        traceback.print_exc()
    finally:
        db.close()

asyncio.run(test())