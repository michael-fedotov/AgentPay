#!/usr/bin/env python3
"""
InboxPay Demo - Clean Implementation
Following the exact specification for AgentMail integration
"""
import uuid
import os
import re
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from pydantic_settings import BaseSettings
from sqlalchemy import Column, String, DateTime, Integer, Text, create_engine, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from agentmail import AgentMail
from dotenv import load_dotenv
import httpx

# Settings
class Settings(BaseSettings):
    agentmail_api_key: str = ""
    demo_inbox_id: str = ""  # bills@...agentmail.to
    user_email: str = "m_fedotov@hotmail.com"
    webhook_secret: str = ""
    db_url: str = "sqlite:///./inboxpay_demo.db"
    
    class Config:
        env_file = ".env"

settings = Settings()
load_dotenv()

# Initialize AgentMail
agentmail_client = AgentMail(api_key=settings.agentmail_api_key)
httpx_client = httpx.AsyncClient(timeout=15.0)

# Database setup
engine = create_engine(settings.db_url, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Models
class Bill(Base):
    __tablename__ = "bills"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    message_id = Column(String, unique=True, nullable=False)
    inbox_id = Column(String, nullable=False)
    thread_id = Column(String, nullable=True)
    from_email = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    
    # Parsed fields
    payee = Column(String, nullable=True)
    amount_cents = Column(Integer, nullable=True)
    due_date_iso = Column(String, nullable=True)  # YYYY-MM-DD
    
    # Status: parsed | failed | autopay | approval
    status = Column(String, default="parsed")
    
    # Agent actions
    agent_reply_sent = Column(Boolean, default=False)
    user_notification_sent = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class EventLog(Base):
    __tablename__ = "event_logs"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    event_type = Column(String, nullable=False)  # webhook_received, bill_parsed, agent_reply, etc.
    message_id = Column(String, nullable=True)
    payload = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

# Create tables
Base.metadata.create_all(bind=engine)

# FastAPI app
app = FastAPI(title="InboxPay Demo", version="1.0.0")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Bill parsing functions
def parse_bill_content(email_text: str) -> Dict[str, Any]:
    """Parse bill information from email content using regex"""
    result = {
        "payee": None,
        "amount_cents": None,
        "due_date_iso": None
    }
    
    # Extract amount (look for various patterns)
    amount_patterns = [
        r"(?:amount\s+due|total\s+due|balance\s+due|pay\s+amount)[:,\s]*\$?(\d+(?:,\d{3})*(?:\.\d{2})?)",
        r"\$(\d+(?:,\d{3})*(?:\.\d{2})?)(?:\s+(?:due|total|amount|balance))?",
        r"(?:total|amount|balance)[:,\s]*\$?(\d+(?:,\d{3})*(?:\.\d{2})?)",
    ]
    
    for pattern in amount_patterns:
        matches = re.findall(pattern, email_text, re.IGNORECASE)
        if matches:
            try:
                amount_str = matches[0].replace(",", "")
                amount = float(amount_str)
                result["amount_cents"] = int(amount * 100)
                break
            except ValueError:
                continue
    
    # Extract due date
    date_patterns = [
        r"\b(\d{4}-\d{2}-\d{2})\b",  # YYYY-MM-DD
        r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b",  # MM/DD/YYYY
        r"\b(jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|aug|august|sep|september|oct|october|nov|november|dec|december)\s+(\d{1,2}),?\s+(\d{4})\b"
    ]
    
    # Try ISO format first
    iso_match = re.search(date_patterns[0], email_text, re.IGNORECASE)
    if iso_match:
        result["due_date_iso"] = iso_match.group(1)
    else:
        # Try MM/DD/YYYY
        us_match = re.search(date_patterns[1], email_text)
        if us_match:
            month, day, year = us_match.groups()
            result["due_date_iso"] = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        else:
            # Try named months
            month_names = {
                'jan': '01', 'january': '01', 'feb': '02', 'february': '02',
                'mar': '03', 'march': '03', 'apr': '04', 'april': '04',
                'may': '05', 'jun': '06', 'june': '06', 'jul': '07', 'july': '07',
                'aug': '08', 'august': '08', 'sep': '09', 'september': '09',
                'oct': '10', 'october': '10', 'nov': '11', 'november': '11',
                'dec': '12', 'december': '12'
            }
            
            named_match = re.search(date_patterns[2], email_text, re.IGNORECASE)
            if named_match:
                month_name, day, year = named_match.groups()
                month_num = month_names.get(month_name.lower())
                if month_num:
                    result["due_date_iso"] = f"{year}-{month_num}-{day.zfill(2)}"
    
    # Extract payee (simple heuristic)
    lines = email_text.split('\n')
    for line in lines[:10]:
        if line.lower().startswith('from:'):
            # Extract company name from From: line
            match = re.search(r'from:\s*([^<@]+)', line, re.IGNORECASE)
            if match:
                payee = match.group(1).strip()
                # Clean up
                payee = re.sub(r'\s*(no-reply|noreply|support|billing)\s*', '', payee, flags=re.IGNORECASE)
                if payee:
                    result["payee"] = payee
                    break
    
    # If no payee found, try to extract from subject or sender
    if not result["payee"]:
        # Look for company names in common patterns
        company_patterns = [
            r'\b([A-Z][a-z]+\s+(?:Electric|Gas|Water|Wireless|Bank|Card|Insurance|Utility))\b',
            r'\b(ComEd|PG&E|Verizon|AT&T|Chase|Wells\s+Fargo|Bank\s+of\s+America)\b'
        ]
        
        for pattern in company_patterns:
            match = re.search(pattern, email_text, re.IGNORECASE)
            if match:
                result["payee"] = match.group(1)
                break
    
    return result

def should_autopay(amount_cents: Optional[int], due_date_iso: Optional[str]) -> bool:
    """Decision engine: autopay if ≤ $150 and due within 10 days"""
    if not amount_cents or not due_date_iso:
        return False
    
    # Check amount
    if amount_cents > 15000:  # $150.00
        return False
    
    # Check due date
    try:
        due_date = datetime.fromisoformat(due_date_iso)
        days_until_due = (due_date - datetime.now()).days
        return 0 <= days_until_due <= 10
    except:
        return False

async def send_agent_reply(bill: Bill, db: Session) -> bool:
    """Send agent reply in-thread"""
    try:
        if should_autopay(bill.amount_cents, bill.due_date_iso):
            # Autopay path
            amount_str = f"${bill.amount_cents/100:.2f}" if bill.amount_cents else "the amount"
            due_date_str = bill.due_date_iso or "the due date"
            
            reply_text = f"""Thank you for your bill.

Payment of {amount_str} has been scheduled for {due_date_str}.

Reference: DRYRUN-{bill.id[:8]}

This is an automated response from your InboxPay agent."""
            
            bill.status = "autopay"
        else:
            # Approval path
            reply_text = f"""Thank you for your bill.

I'm requesting either a 2-week extension or a 3-month payment plan for this bill.

I'll follow up once I receive confirmation from you.

Reference: APPROVAL-{bill.id[:8]}

This is an automated response from your InboxPay agent."""
            
            bill.status = "approval"
        
        # Send reply using AgentMail
        response = agentmail_client.inboxes.messages.send(
            inbox_id=bill.inbox_id,
            to=bill.from_email,
            subject=f"Re: {bill.subject}",
            text=reply_text,
            in_reply_to=bill.message_id,
            thread_id=bill.thread_id
        )
        
        bill.agent_reply_sent = True
        bill.updated_at = datetime.utcnow()
        db.commit()
        
        # Log the action
        log_event(db, "agent_reply_sent", bill.message_id, {
            "bill_id": bill.id,
            "reply_type": bill.status,
            "amount_cents": bill.amount_cents
        })
        
        return True
        
    except Exception as e:
        log_event(db, "agent_reply_failed", bill.message_id, {"error": str(e)})
        return False

async def notify_user(bill: Bill, db: Session) -> bool:
    """Send summary email to user"""
    try:
        if bill.status == "autopay":
            subject = f"InboxPay: Payment Scheduled - ${bill.amount_cents/100:.2f}"
            summary = f"Your agent scheduled a payment of ${bill.amount_cents/100:.2f} to {bill.payee or 'the vendor'} for {bill.due_date_iso or 'the due date'}."
        else:
            subject = f"InboxPay: Extension Requested - {bill.payee or 'Vendor'}"
            summary = f"Your agent requested a payment extension for the bill from {bill.payee or 'the vendor'}."
        
        notification_text = f"""InboxPay Agent Summary

Bill Processed: {bill.subject}
From: {bill.from_email}
Amount: ${bill.amount_cents/100:.2f if bill.amount_cents else 'Unknown'}
Due Date: {bill.due_date_iso or 'Unknown'}

Action Taken: {summary}

Reference: {bill.id}
Processed: {bill.created_at.strftime('%Y-%m-%d %H:%M:%S')} UTC

Your InboxPay Agent"""
        
        # Send notification to user
        response = agentmail_client.inboxes.messages.send(
            inbox_id=bill.inbox_id,
            to=settings.user_email,
            subject=subject,
            text=notification_text
        )
        
        bill.user_notification_sent = True
        bill.updated_at = datetime.utcnow()
        db.commit()
        
        # Log the action
        log_event(db, "user_notification_sent", bill.message_id, {
            "bill_id": bill.id,
            "user_email": settings.user_email
        })
        
        return True
        
    except Exception as e:
        log_event(db, "user_notification_failed", bill.message_id, {"error": str(e)})
        return False

def log_event(db: Session, event_type: str, message_id: Optional[str], payload: Any):
    """Log an event to the database"""
    try:
        event = EventLog(
            event_type=event_type,
            message_id=message_id,
            payload=json.dumps(payload) if payload else None
        )
        db.add(event)
        db.commit()
    except Exception as e:
        print(f"Failed to log event: {e}")

# API Endpoints

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    """Main dashboard showing parsed bills"""
    bills = db.query(Bill).order_by(Bill.created_at.desc()).limit(20).all()
    
    # Stats
    total_bills = db.query(Bill).count()
    autopay_bills = db.query(Bill).filter(Bill.status == "autopay").count()
    approval_bills = db.query(Bill).filter(Bill.status == "approval").count()
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "bills": bills,
        "stats": {
            "total": total_bills,
            "autopay": autopay_bills,
            "approval": approval_bills
        }
    })

@app.get("/health")
async def health():
    """Health check"""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

@app.post("/api/agentmail/webhook")
async def agentmail_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle AgentMail webhooks - A) Ingestion"""
    try:
        payload = await request.json()
        
        # Log webhook received
        log_event(db, "webhook_received", None, payload)
        
        event_type = payload.get("type")
        if event_type != "message.received":
            return {"status": "ignored", "reason": f"Event type {event_type} not handled"}
        
        data = payload.get("data", {})
        message_id = data.get("id")
        inbox_id = data.get("inbox_id")
        thread_id = data.get("thread_id")
        from_emails = data.get("from", [])
        subject = data.get("subject", "")
        
        if not message_id or not inbox_id:
            raise HTTPException(400, "Missing required fields")
        
        # Idempotency check
        existing_bill = db.query(Bill).filter(Bill.message_id == message_id).first()
        if existing_bill:
            return {"status": "duplicate", "bill_id": existing_bill.id}
        
        # Fetch full message content
        try:
            message = agentmail_client.inboxes.messages.get(
                inbox_id=inbox_id,
                message_id=message_id
            )
        except Exception as e:
            log_event(db, "message_fetch_failed", message_id, {"error": str(e)})
            raise HTTPException(500, f"Failed to fetch message: {str(e)}")
        
        # Build email content for parsing
        email_content = f"From: {from_emails[0] if from_emails else 'Unknown'}\n"
        email_content += f"Subject: {subject}\n\n"
        if hasattr(message, 'text') and message.text:
            email_content += message.text
        if hasattr(message, 'html') and message.html:
            email_content += f"\n\nHTML: {message.html}"
        
        # B) Understanding - Parse the bill
        parsed_data = parse_bill_content(email_content)
        
        # Create bill record
        bill = Bill(
            message_id=message_id,
            inbox_id=inbox_id,
            thread_id=thread_id,
            from_email=from_emails[0] if from_emails else "unknown@example.com",
            subject=subject,
            payee=parsed_data["payee"],
            amount_cents=parsed_data["amount_cents"],
            due_date_iso=parsed_data["due_date_iso"],
            status="parsed" if parsed_data["amount_cents"] else "failed"
        )
        
        db.add(bill)
        db.commit()
        db.refresh(bill)
        
        # Log parsing result
        log_event(db, "bill_parsed", message_id, {
            "bill_id": bill.id,
            "payee": bill.payee,
            "amount_cents": bill.amount_cents,
            "due_date_iso": bill.due_date_iso,
            "status": bill.status
        })
        
        # C) Acting - Send agent reply and notify user
        if bill.status == "parsed":
            # Send agent reply in-thread
            await send_agent_reply(bill, db)
            
            # Notify user
            await notify_user(bill, db)
        
        return {
            "status": "processed",
            "bill_id": bill.id,
            "parsed_data": parsed_data,
            "agent_action": bill.status
        }
        
    except Exception as e:
        log_event(db, "webhook_error", None, {"error": str(e)})
        raise HTTPException(500, f"Webhook processing failed: {str(e)}")

@app.post("/api/send-test-bill")
async def send_test_bill(db: Session = Depends(get_db)):
    """Send a test bill to the inbox for demo purposes"""
    try:
        test_bills = [
            {
                "subject": "ComEd Electric Bill - Account 123456",
                "payee": "Commonwealth Edison",
                "amount": 89.50,
                "due_days": 8  # Should trigger autopay
            },
            {
                "subject": "Chase Credit Card Statement",
                "payee": "Chase Bank",
                "amount": 245.75,
                "due_days": 5  # Over $150, should trigger approval
            },
            {
                "subject": "Blue Cross Health Insurance Premium",
                "payee": "Blue Cross Blue Shield",
                "amount": 125.00,
                "due_days": 15  # Over 10 days, should trigger approval
            }
        ]
        
        # Pick a random test bill
        import random
        test_bill = random.choice(test_bills)
        
        due_date = (datetime.now() + timedelta(days=test_bill["due_days"])).strftime("%B %d, %Y")
        due_date_iso = (datetime.now() + timedelta(days=test_bill["due_days"])).strftime("%Y-%m-%d")
        
        bill_content = f"""From: {test_bill["payee"]} <billing@{test_bill["payee"].lower().replace(" ", "")}.com>
Subject: {test_bill["subject"]}

Dear Customer,

Your {test_bill["subject"].lower()} is now available.

BILLING SUMMARY:
Previous Balance: $0.00
Current Charges: ${test_bill["amount"]:.2f}
Total Amount Due: ${test_bill["amount"]:.2f}

Due Date: {due_date}

Please pay by the due date to avoid late fees.

Thank you for your business!

{test_bill["payee"]}
This is an automated message."""
        
        # Send to the inbox
        response = agentmail_client.inboxes.messages.send(
            inbox_id=settings.demo_inbox_id,
            to=settings.demo_inbox_id,  # Send to self
            subject=test_bill["subject"],
            text=bill_content,
            labels=["test-bill", "demo"]
        )
        
        log_event(db, "test_bill_sent", response.message_id, test_bill)
        
        return {
            "status": "sent",
            "message_id": response.message_id,
            "test_bill": test_bill,
            "expected_action": "autopay" if should_autopay(int(test_bill["amount"] * 100), due_date_iso) else "approval"
        }
        
    except Exception as e:
        raise HTTPException(500, f"Failed to send test bill: {str(e)}")

@app.get("/api/bills")
async def get_bills(db: Session = Depends(get_db)):
    """Get all bills for API access"""
    bills = db.query(Bill).order_by(Bill.created_at.desc()).all()
    return [
        {
            "id": bill.id,
            "subject": bill.subject,
            "from_email": bill.from_email,
            "payee": bill.payee,
            "amount_cents": bill.amount_cents,
            "amount_dollars": bill.amount_cents / 100 if bill.amount_cents else None,
            "due_date_iso": bill.due_date_iso,
            "status": bill.status,
            "agent_reply_sent": bill.agent_reply_sent,
            "user_notification_sent": bill.user_notification_sent,
            "created_at": bill.created_at.isoformat()
        }
        for bill in bills
    ]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
