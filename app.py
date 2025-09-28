import uuid
import os
import re
import json
from datetime import datetime
from typing import Optional, List, Dict, Any

import httpx
from fastapi import FastAPI, Request, HTTPException
from agentmail import AgentMail
from dotenv import load_dotenv
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from pydantic_settings import BaseSettings
from sqlalchemy import Column, String, DateTime, Boolean, Integer, Text, ForeignKey, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship

# Conditional Gemini import
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False


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
    gemini_api_key: str = ""
    db_url: str = "sqlite:///./inboxpay.db"

    class Config:
        env_file = ".env"


settings = Settings()

# Load environment variables and initialize AgentMail client
load_dotenv()
agentmail_client = AgentMail(api_key=settings.agentmail_api_key)

# Initialize Gemini client if API key is available
gemini_client = None
if GEMINI_AVAILABLE and settings.gemini_api_key:
    genai.configure(api_key=settings.gemini_api_key)
    gemini_client = genai.GenerativeModel('gemini-pro')

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


# Regex fallback extractors
def parse_amount_cents(text: str) -> Optional[int]:
    """Extract amount in cents from text using regex patterns"""
    # Patterns to match various amount formats
    patterns = [
        r"(?:amount\s+due|total\s+due|minimum\s+due|balance\s+due)[:,\s]*\$?(\d+(?:,\d{3})*(?:\.\d{2})?)",
        r"\$(\d+(?:,\d{3})*(?:\.\d{2})?)(?:\s+(?:due|total|amount|balance))?",
        r"(?:pay|amount|total|due)[:,\s]*\$?(\d+(?:,\d{3})*(?:\.\d{2})?)",
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            # Take the first match and convert to cents
            amount_str = matches[0].replace(",", "")
            try:
                amount = float(amount_str)
                return int(amount * 100)  # Convert to cents
            except ValueError:
                continue
    
    return None


def parse_due_date_iso(text: str) -> Optional[str]:
    """Extract due date and convert to ISO format (YYYY-MM-DD)"""
    # Pattern for YYYY-MM-DD
    iso_pattern = r"\b(\d{4}-\d{2}-\d{2})\b"
    match = re.search(iso_pattern, text)
    if match:
        return match.group(1)
    
    # Pattern for MM/DD/YYYY
    us_pattern = r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b"
    match = re.search(us_pattern, text)
    if match:
        month, day, year = match.groups()
        return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
    
    # Pattern for "Oct 05, 2025" or "October 5, 2025"
    month_names = {
        'jan': '01', 'january': '01',
        'feb': '02', 'february': '02', 
        'mar': '03', 'march': '03',
        'apr': '04', 'april': '04',
        'may': '05', 'may': '05',
        'jun': '06', 'june': '06',
        'jul': '07', 'july': '07',
        'aug': '08', 'august': '08',
        'sep': '09', 'september': '09',
        'oct': '10', 'october': '10',
        'nov': '11', 'november': '11',
        'dec': '12', 'december': '12'
    }
    
    named_pattern = r"\b(jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|aug|august|sep|september|oct|october|nov|november|dec|december)\s+(\d{1,2}),?\s+(\d{4})\b"
    match = re.search(named_pattern, text, re.IGNORECASE)
    if match:
        month_name, day, year = match.groups()
        month_num = month_names.get(month_name.lower())
        if month_num:
            return f"{year}-{month_num}-{day.zfill(2)}"
    
    return None


def regex_fallback(email_text: str) -> Dict[str, Any]:
    """Extract bill information using regex patterns as fallback"""
    result = {
        "payee": None,
        "amount_cents": None,
        "due_date_iso": None
    }
    
    # Extract amount
    result["amount_cents"] = parse_amount_cents(email_text)
    
    # Extract due date
    result["due_date_iso"] = parse_due_date_iso(email_text)
    
    # Extract payee (simple heuristic - look for email domain or sender info)
    lines = email_text.split('\n')
    for line in lines[:10]:  # Check first 10 lines
        # Look for "From:" headers
        if line.lower().startswith('from:'):
            # Extract company name from email
            match = re.search(r'from:\s*([^<@]+)', line, re.IGNORECASE)
            if match:
                payee = match.group(1).strip()
                # Clean up common patterns
                payee = re.sub(r'\s*(no-reply|noreply|support|billing)\s*', '', payee, flags=re.IGNORECASE)
                if payee:
                    result["payee"] = payee
                    break
        
        # Look for company names in subject or early content
        if any(word in line.lower() for word in ['electric', 'gas', 'water', 'internet', 'phone', 'cable', 'credit']):
            # Extract potential company name
            words = line.split()
            for i, word in enumerate(words):
                if any(company_type in word.lower() for company_type in ['electric', 'gas', 'water', 'internet', 'phone', 'cable', 'credit']):
                    # Take 1-2 words before this as company name
                    if i > 0:
                        result["payee"] = " ".join(words[max(0, i-1):i+1])
                        break
            if result["payee"]:
                break
    
    return result


# LLM-based extraction with Gemini
async def llm_extract(email_text: str) -> Dict[str, Any]:
    """Extract bill information using Gemini LLM with JSON validation and regex fallback"""
    
    # If Gemini is not available, use regex fallback immediately
    if not gemini_client:
        print("⚠️ Gemini client not available, using regex fallback")
        return regex_fallback(email_text)
    
    system_prompt = """You are a deterministic bill parser. Output ONLY valid JSON:
{"payee": string, "amount_cents": number, "due_date_iso": string|null}
Rules: normalize amount to cents (pick smallest positive Amount Due/Total Due).
due_date_iso is YYYY-MM-DD or null. Derive payee from headers/brand. No extra text."""
    
    user_prompt = f"Extract bill fields from this email:\n---BEGIN---\n{email_text}\n---END---"
    
    try:
        # Combine system and user prompts for Gemini
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        
        # Generate response from Gemini
        response = await httpx_client.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent",
            headers={
                "Content-Type": "application/json",
            },
            params={"key": settings.gemini_api_key},
            json={
                "contents": [{
                    "parts": [{"text": full_prompt}]
                }],
                "generationConfig": {
                    "temperature": 0.1,
                    "maxOutputTokens": 200
                }
            },
            timeout=10.0
        )
        
        if response.status_code == 200:
            result = response.json()
            if "candidates" in result and len(result["candidates"]) > 0:
                generated_text = result["candidates"][0]["content"]["parts"][0]["text"].strip()
                
                # Try to parse as JSON
                try:
                    parsed_data = json.loads(generated_text)
                    
                    # Validate the required fields exist and have correct types
                    if (isinstance(parsed_data, dict) and 
                        "payee" in parsed_data and 
                        "amount_cents" in parsed_data and 
                        "due_date_iso" in parsed_data):
                        
                        # Ensure amount_cents is an integer or can be converted
                        if parsed_data["amount_cents"] is not None:
                            try:
                                parsed_data["amount_cents"] = int(parsed_data["amount_cents"])
                            except (ValueError, TypeError):
                                parsed_data["amount_cents"] = None
                        
                        # Ensure due_date_iso is string or null
                        if parsed_data["due_date_iso"] is not None and not isinstance(parsed_data["due_date_iso"], str):
                            parsed_data["due_date_iso"] = None
                        
                        print(f"✅ LLM extraction successful: {parsed_data}")
                        return parsed_data
                    else:
                        print("⚠️ LLM response missing required fields, using regex fallback")
                
                except json.JSONDecodeError as e:
                    print(f"⚠️ LLM response not valid JSON: {e}, using regex fallback")
            else:
                print("⚠️ No candidates in LLM response, using regex fallback")
        else:
            print(f"⚠️ LLM API error {response.status_code}, using regex fallback")
    
    except Exception as e:
        print(f"⚠️ LLM extraction failed: {e}, using regex fallback")
    
    # Fallback to regex extraction
    return regex_fallback(email_text)


# AgentMail helpers using official client
def agentmail_get_inbox(inbox_id: str):
    """Get inbox information from AgentMail"""
    try:
        retrieved_inbox = agentmail_client.inboxes.get(inbox_id=inbox_id)
        return {"success": True, "inbox": retrieved_inbox}
    except Exception as e:
        return {"success": False, "error": str(e)}


def agentmail_send(
    inbox_id: str, 
    to: str, 
    subject: str, 
    text: str, 
    html: Optional[str] = None,
    labels: Optional[List[str]] = None
):
    """Send a new message via AgentMail"""
    try:
        message_params = {
            "inbox_id": inbox_id,
            "to": to,
            "subject": subject,
            "text": text
        }
        
        if html:
            message_params["html"] = html
        if labels:
            message_params["labels"] = labels
            
        sent_message = agentmail_client.inboxes.messages.send(**message_params)
        return {
            "success": True, 
            "message_id": sent_message.message_id,
            "message": sent_message
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def agentmail_get_messages(inbox_id: str):
    """Get all messages from an inbox"""
    try:
        all_messages = agentmail_client.inboxes.messages.list(inbox_id=inbox_id)
        return {
            "success": True,
            "count": all_messages.count,
            "messages": all_messages.messages
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def agentmail_get_message(inbox_id: str, message_id: str):
    """Get a specific message by ID"""
    try:
        message = agentmail_client.inboxes.messages.get(
            inbox_id=inbox_id, 
            message_id=message_id
        )
        return {"success": True, "message": message}
    except Exception as e:
        return {"success": False, "error": str(e)}


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


# Webhook handler
@app.post("/webhook/agentmail")
async def agentmail_webhook(request: Request):
    """Handle AgentMail webhook events - processes incoming bills automatically"""
    try:
        # Get webhook payload
        payload = await request.json()
        headers = dict(request.headers)
        
        # Log incoming webhook
        db = next(get_db())
        log_event(db, "webhook_received", payload)
        
        print(f"📥 Webhook received: {payload}")
        
        # Verify webhook signature if secret is configured
        if settings.webhook_secret:
            signature = headers.get("x-agentmail-signature", "")
            if not verify_webhook_signature(await request.body(), signature, settings.webhook_secret):
                print("❌ Invalid webhook signature")
                raise HTTPException(status_code=401, detail="Invalid signature")
        
        # Extract event data
        event_type = payload.get("type", "unknown")
        event_data = payload.get("data", {})
        
        print(f"📋 Event type: {event_type}")
        
        # Handle different event types
        if event_type == "message.received":
            result = await process_incoming_message(db, event_data)
            return {"status": "processed", "result": result}
        
        elif event_type == "message.sent":
            print("📤 Outgoing message webhook - no action needed")
            return {"status": "acknowledged", "message": "Outgoing message logged"}
        
        else:
            print(f"⚠️ Unknown event type: {event_type}")
            return {"status": "acknowledged", "message": f"Unknown event type: {event_type}"}
    
    except Exception as e:
        print(f"❌ Webhook processing error: {e}")
        # Log error
        try:
            db = next(get_db())
            log_event(db, "webhook_error", {"error": str(e), "payload": payload})
        except:
            pass
        raise HTTPException(status_code=500, detail=f"Webhook processing failed: {str(e)}")


async def process_incoming_message(db: Session, event_data: Dict[str, Any]) -> Dict[str, Any]:
    """Process an incoming message event from AgentMail webhook"""
    try:
        # Extract message details from webhook
        inbox_id = event_data.get("inbox_id")
        message_id = event_data.get("message_id")
        from_email = event_data.get("from")
        subject = event_data.get("subject", "")
        
        print(f"📧 Processing message: {message_id} from {from_email}")
        
        if not inbox_id or not message_id:
            return {"success": False, "error": "Missing inbox_id or message_id"}
        
        # Get full message content from AgentMail
        message_result = agentmail_get_message(inbox_id, message_id)
        if not message_result["success"]:
            return {"success": False, "error": f"Failed to fetch message: {message_result.get('error')}"}
        
        full_message = message_result["message"]
        
        # Combine message content for extraction
        email_content = build_email_content_for_extraction(full_message, from_email, subject)
        
        print(f"📄 Email content length: {len(email_content)} characters")
        
        # Extract bill information using LLM/regex
        bill_data = await llm_extract(email_content)
        
        print(f"🔍 Extracted bill data: {bill_data}")
        
        # Check if this looks like a bill
        is_potential_bill = (
            bill_data.get("amount_cents") is not None or
            bill_data.get("due_date_iso") is not None or
            any(keyword in email_content.lower() for keyword in [
                "bill", "invoice", "payment", "due", "amount", "balance", "statement"
            ])
        )
        
        if not is_potential_bill:
            print("📋 Email doesn't appear to be a bill - skipping payment processing")
            return {
                "success": True, 
                "message": "Email processed but not identified as a bill",
                "bill_detected": False
            }
        
        # Save bill to database
        bill = create_bill_record(
            db=db,
            inbox_id=inbox_id,
            message_id=message_id,
            from_email=from_email,
            subject=subject,
            payee=bill_data.get("payee"),
            amount_cents=bill_data.get("amount_cents"),
            due_date_iso=bill_data.get("due_date_iso")
        )
        
        print(f"💾 Bill saved to database: {bill.id}")
        
        # Process payment if amount is available and demo mode is enabled
        payment_result = None
        if bill.amount_cents and bill.amount_cents > 0:
            payment_result = await process_bill_payment(db, bill)
            print(f"💳 Payment processing result: {payment_result}")
        
        # Send confirmation email back to sender
        confirmation_result = await send_bill_confirmation(
            inbox_id=inbox_id,
            to_email=from_email,
            bill=bill,
            payment_result=payment_result
        )
        
        return {
            "success": True,
            "bill_id": bill.id,
            "bill_detected": True,
            "amount_cents": bill.amount_cents,
            "payee": bill.payee,
            "due_date": bill.due_date,
            "payment_processed": payment_result is not None,
            "confirmation_sent": confirmation_result.get("success", False)
        }
    
    except Exception as e:
        print(f"❌ Error processing incoming message: {e}")
        log_event(db, "message_processing_error", {"error": str(e), "event_data": event_data})
        return {"success": False, "error": str(e)}


def build_email_content_for_extraction(message, from_email: str, subject: str) -> str:
    """Build comprehensive email content for bill extraction"""
    content_parts = [f"From: {from_email}", f"Subject: {subject}", ""]
    
    # Add text content
    if hasattr(message, 'text') and message.text:
        content_parts.append("TEXT CONTENT:")
        content_parts.append(message.text)
        content_parts.append("")
    
    # Add HTML content (basic text extraction)
    if hasattr(message, 'html') and message.html:
        content_parts.append("HTML CONTENT:")
        # Simple HTML stripping for extraction
        html_text = message.html
        # Remove common HTML tags for basic text extraction
        import re
        html_text = re.sub(r'<[^>]+>', ' ', html_text)
        html_text = re.sub(r'\s+', ' ', html_text).strip()
        content_parts.append(html_text)
    
    return "\n".join(content_parts)


def create_bill_record(db: Session, inbox_id: str, message_id: str, from_email: str, 
                      subject: str, payee: Optional[str], amount_cents: Optional[int], 
                      due_date_iso: Optional[str]) -> Bill:
    """Create a new bill record in the database"""
    
    # Parse due date if provided
    due_date = None
    if due_date_iso:
        try:
            due_date = datetime.fromisoformat(due_date_iso.replace('Z', '+00:00'))
        except ValueError:
            print(f"⚠️ Invalid due date format: {due_date_iso}")
    
    bill = Bill(
        id=cuid(),
        inbox_id=inbox_id,
        message_id=message_id,
        from_email=from_email,
        subject=subject,
        payee=payee,
        amount_cents=amount_cents,
        due_date=due_date,
        status="parsed" if amount_cents else "received"
    )
    
    db.add(bill)
    db.commit()
    db.refresh(bill)
    
    # Log the bill creation
    log_event(db, "bill_created", {
        "bill_id": bill.id,
        "payee": payee,
        "amount_cents": amount_cents,
        "due_date": due_date_iso
    })
    
    return bill


async def process_bill_payment(db: Session, bill: Bill) -> Optional[Dict[str, Any]]:
    """Process payment for a bill using Method API"""
    try:
        print(f"💳 Processing payment for bill {bill.id}: ${bill.amount_cents/100:.2f}")
        
        # Call Method API for payment (dry run in demo mode)
        payment_result = await method_payment_dryrun(bill.id, bill.amount_cents)
        
        # Create payment record
        payment = Payment(
            id=cuid(),
            bill_id=bill.id,
            method_payment_id=payment_result.get("methodPaymentId"),
            amount_cents=bill.amount_cents,
            dry_run=payment_result.get("dryRun", True),
            status="simulated" if payment_result.get("dryRun") else "pending"
        )
        
        db.add(payment)
        
        # Update bill status
        bill.status = "scheduled" if payment_result.get("ok") else "failed"
        bill.updated_at = datetime.utcnow()
        
        db.commit()
        
        # Log payment processing
        log_event(db, "payment_processed", {
            "bill_id": bill.id,
            "payment_id": payment.id,
            "amount_cents": bill.amount_cents,
            "dry_run": payment.dry_run,
            "status": payment.status
        })
        
        return {
            "success": payment_result.get("ok", False),
            "payment_id": payment.id,
            "method_payment_id": payment.method_payment_id,
            "dry_run": payment.dry_run,
            "status": payment.status
        }
    
    except Exception as e:
        print(f"❌ Payment processing failed: {e}")
        bill.status = "failed"
        db.commit()
        
        log_event(db, "payment_error", {
            "bill_id": bill.id,
            "error": str(e)
        })
        return None


async def send_bill_confirmation(inbox_id: str, to_email: str, bill: Bill, 
                                payment_result: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Send confirmation email back to the bill sender"""
    try:
        # Build confirmation message
        if payment_result and payment_result.get("success"):
            status = "✅ Payment Scheduled" if payment_result.get("dry_run") else "✅ Payment Processing"
            details = f"Payment of ${bill.amount_cents/100:.2f} has been scheduled for processing."
        else:
            status = "📋 Bill Received"
            details = "Your bill has been received and logged in our system."
        
        subject = f"AgentPay: {status} - {bill.payee or 'Bill Processed'}"
        
        text_content = f"""
Hello,

Your bill has been processed by AgentPay:

Bill Details:
- Payee: {bill.payee or 'Not specified'}
- Amount: ${bill.amount_cents/100:.2f if bill.amount_cents else 'Not specified'}
- Due Date: {bill.due_date.strftime('%Y-%m-%d') if bill.due_date else 'Not specified'}
- Status: {status}

{details}

Bill ID: {bill.id}
Processed: {bill.created_at.strftime('%Y-%m-%d %H:%M:%S')} UTC

This is an automated message from AgentPay.
        """.strip()
        
        # Send confirmation
        send_result = agentmail_send(
            inbox_id=inbox_id,
            to=to_email,
            subject=subject,
            text=text_content,
            labels=["agentpay-confirmation", "automated"]
        )
        
        return send_result
    
    except Exception as e:
        print(f"❌ Failed to send confirmation: {e}")
        return {"success": False, "error": str(e)}


def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify AgentMail webhook signature for security"""
    try:
        import hmac
        import hashlib
        
        # Compute expected signature
        expected = hmac.new(
            secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        # Compare signatures
        return hmac.compare_digest(signature, f"sha256={expected}")
    except Exception as e:
        print(f"❌ Signature verification error: {e}")
        return False


def log_event(db: Session, event_kind: str, payload: Any):
    """Log an event to the database"""
    try:
        event = EventLog(
            id=cuid(),
            kind=event_kind,
            payload=json.dumps(payload) if payload else None
        )
        db.add(event)
        db.commit()
    except Exception as e:
        print(f"⚠️ Failed to log event: {e}")


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


@app.get("/test/agentmail")
async def test_agentmail():
    """Test AgentMail integration"""
    if not settings.agentmail_api_key:
        return {"error": "AGENTMAIL_API_KEY not set in environment"}
    
    if not settings.demo_inbox_id:
        return {"error": "DEMO_INBOX_ID not set in environment"}
    
    # Test getting inbox info
    inbox_result = agentmail_get_inbox(settings.demo_inbox_id)
    
    # Test getting messages
    messages_result = agentmail_get_messages(settings.demo_inbox_id)
    
    return {
        "status": "AgentMail test completed",
        "inbox": inbox_result,
        "messages": messages_result,
        "config": {
            "demo_inbox_id": settings.demo_inbox_id,
            "demo_agent_to": settings.demo_agent_to,
            "demo_mode": settings.demo_mode
        }
    }


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Render the main dashboard"""
    return templates.TemplateResponse("index.html", {"request": request})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
