import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from pydantic_settings import BaseSettings
from sqlalchemy import Column, String, DateTime, Boolean, Integer, Text, ForeignKey, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship


# Settings
class Settings(BaseSettings):
    agentmail_api_key: str = ""
    method_api_key: str = ""
    user_email: str = "you@example.com"
    demo_mode: bool = True
    webhook_secret: str = ""
    agentmail_base: str = "https://api.agentmail.to/v0"
    demo_inbox_id: str = ""
    demo_agent_to: str = ""
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    db_url: str = "sqlite:///./inboxpay.db"

    class Config:
        env_file = ".env"


settings = Settings()

# Global HTTP client
httpx_client = httpx.AsyncClient(timeout=15.0)

# Database setup
engine = create_engine(settings.db_url, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# Utility function
def cuid() -> str:
    """Generate a CUID-like identifier using uuid4"""
    return str(uuid.uuid4())


# AgentMail helpers
am_headers = {"Authorization": f"Bearer {settings.agentmail_api_key}"}


async def agentmail_get_raw(inbox_id: str, message_id: str) -> Dict[str, Any]:
    """Get raw message from AgentMail"""
    url = f"{settings.agentmail_base}/inboxes/{inbox_id}/messages/{message_id}/raw"
    try:
        response = await httpx_client.get(url, headers=am_headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": str(e)}


async def agentmail_reply(
    inbox_id: str, 
    message_id: str, 
    subject: str, 
    text: str, 
    html: Optional[str] = None
) -> Dict[str, Any]:
    """Reply to a message via AgentMail"""
    url = f"{settings.agentmail_base}/inboxes/{inbox_id}/messages/{message_id}/reply"
    
    payload = {
        "subject": subject,
        "text": text
    }
    if html:
        payload["html"] = html
    
    try:
        response = await httpx_client.post(url, headers=am_headers, json=payload)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": str(e)}


async def agentmail_send(
    inbox_id: str, 
    to_list: List[str], 
    subject: str, 
    text: str, 
    html: Optional[str] = None
) -> Dict[str, Any]:
    """Send a new message via AgentMail"""
    url = f"{settings.agentmail_base}/inboxes/{inbox_id}/messages"
    
    payload = {
        "to": to_list,
        "subject": subject,
        "text": text
    }
    if html:
        payload["html"] = html
    
    try:
        response = await httpx_client.post(url, headers=am_headers, json=payload)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": str(e)}


# Method API shim
async def method_payment_dryrun(bill_id: str, amount_cents: int) -> Dict[str, Any]:
    """Create a dry run payment via Method API or simulate in demo mode"""
    
    # Demo mode or no API key - return simulated success
    if settings.demo_mode or not settings.method_api_key:
        return {
            "ok": True,
            "dryRun": True,
            "methodPaymentId": None
        }
    
    # Real Method API call
    url = "https://api.methodfi.com/payments"
    headers = {
        "Authorization": f"Bearer {settings.method_api_key}",
        "Method-Version": "2023-01-01",
        "Content-Type": "application/json"
    }
    
    payload = {
        "amount": amount_cents,
        "source": "src_demo_123",
        "destination": "dest_demo_456", 
        "description": f"Payment for bill {bill_id}",
        "dry_run": True
    }
    
    try:
        response = await httpx_client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        
        return {
            "ok": True,
            "dryRun": True,
            "methodPaymentId": result.get("id")
        }
    except Exception as e:
        return {
            "ok": False,
            "dryRun": False,
            "methodPaymentId": None,
            "error": str(e)
        }


# Models
class Bill(Base):
    __tablename__ = "bills"

    id = Column(String, primary_key=True, default=cuid)
    inbox_id = Column(String, nullable=False)
    thread_id = Column(String, nullable=True)
    message_id = Column(String, unique=True, nullable=False)
    from_email = Column(String, nullable=True)
    subject = Column(String, nullable=True)
    payee = Column(String, nullable=True)
    amount_cents = Column(Integer, nullable=True)
    due_date = Column(DateTime, nullable=True)
    status = Column(String, default="received")  # received|parsed|scheduled|failed|approved
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    payments = relationship("Payment", back_populates="bill", cascade="all, delete-orphan")


class Payment(Base):
    __tablename__ = "payments"

    id = Column(String, primary_key=True, default=cuid)
    bill_id = Column(String, ForeignKey("bills.id", ondelete="CASCADE"), nullable=False)
    method_payment_id = Column(String, nullable=True)
    amount_cents = Column(Integer, nullable=False)
    dry_run = Column(Boolean, default=True)
    status = Column(String, default="simulated")  # simulated|pending|succeeded|failed
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship
    bill = relationship("Bill", back_populates="payments")


class EventLog(Base):
    __tablename__ = "event_logs"

    id = Column(String, primary_key=True, default=cuid)
    kind = Column(String, nullable=False)
    payload = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# Create tables
Base.metadata.create_all(bind=engine)

# FastAPI app
app = FastAPI(title="InboxPay FastAPI", version="0.1.0")

# Static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Health endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


# Route placeholders
@app.post("/webhook/agentmail")
async def agentmail_webhook(request: Request):
    """Handle AgentMail webhook events"""
    # TODO: Implement AgentMail webhook handling
    return {"status": "received", "message": "AgentMail webhook placeholder"}


@app.post("/dev/send-bill")
async def dev_send_bill(request: Request):
    """Development endpoint to send a test bill"""
    # TODO: Implement bill sending functionality
    return {"status": "sent", "message": "Bill sending placeholder"}


@app.get("/snapshot")
async def get_snapshot():
    """Get current system snapshot"""
    # TODO: Implement system snapshot functionality
    return {"status": "snapshot", "message": "Snapshot placeholder"}


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Render the main dashboard"""
    return templates.TemplateResponse("index.html", {"request": request})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
