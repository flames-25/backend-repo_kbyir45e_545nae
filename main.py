import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from database import create_document
from schemas import ContactMessage
import requests

TWILIO_WHATSAPP_ENABLED = os.getenv("TWILIO_WHATSAPP_ENABLED", "false").lower() == "true"
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM")  # e.g., 'whatsapp:+14155238886'
OWNER_WHATSAPP_TO = os.getenv("OWNER_WHATSAPP_TO")        # e.g., 'whatsapp:+919782017257'

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI Backend!"}

@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}

@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    
    try:
        # Try to import database module
        from database import db
        
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            
            # Try to list collections to verify connectivity
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]  # Show first 10 collections
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
            
    except ImportError:
        response["database"] = "❌ Database module not found (run enable-database first)"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    
    # Check environment variables
    import os
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    
    return response


# WhatsApp sending via Twilio API

def send_whatsapp_message(body: str) -> bool:
    if not TWILIO_WHATSAPP_ENABLED:
        return False
    required = [TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM, OWNER_WHATSAPP_TO]
    if not all(required):
        return False

    url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
    data = {
        "From": TWILIO_WHATSAPP_FROM,
        "To": OWNER_WHATSAPP_TO,
        "Body": body,
    }
    try:
        r = requests.post(url, data=data, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN), timeout=10)
        return r.status_code in (200, 201)
    except Exception:
        return False


class ContactIn(BaseModel):
    name: str
    phone: str
    email: Optional[str] = None
    message: str

@app.post("/api/contact")
def create_contact(payload: ContactIn):
    # Validate with schema and store in DB
    msg = ContactMessage(**payload.model_dump())
    try:
        doc_id = create_document("contactmessage", msg)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)[:120]}")

    # Send WhatsApp notification (best-effort, non-blocking result)
    body = (
        f"New Contact Message\n"
        f"Name: {msg.name}\n"
        f"Phone: {msg.phone}\n"
        f"Email: {msg.email or '-'}\n"
        f"Message: {msg.message[:500]}"
    )
    send_whatsapp_message(body)

    return {"ok": True, "id": doc_id}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
