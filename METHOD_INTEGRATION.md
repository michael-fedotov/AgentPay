# Method API Integration Guide

## Overview
This guide shows how to integrate Method API for real payments after the demo.

## Current Demo State
- Uses `DRYRUN` payments (no real money)
- All payment logic is in `demo_app.py`
- Bills are processed and "paid" automatically

## Method API Integration Steps

### 1. Install Method SDK
```bash
pip install method-python
```

### 2. Add Method Settings
Add to your `.env` file:
```env
METHOD_API_KEY=your_method_api_key
METHOD_ENVIRONMENT=sandbox  # or production
```

### 3. Update Settings Class
```python
class Settings(BaseSettings):
    # ... existing settings ...
    method_api_key: str = ""
    method_environment: str = "sandbox"
```

### 4. Initialize Method Client
```python
from method import Method

method_client = Method(
    api_key=settings.method_api_key,
    environment=settings.method_environment
)
```

### 5. Replace DRYRUN Payment Logic

**Current code in `send_agent_reply()`:**
```python
reply_text = f"""Payment of {amount_str} has been scheduled for {due_date_str}.
Reference: DRYRUN-{bill.id[:8]}"""
```

**Replace with Method API:**
```python
async def process_real_payment(bill: Bill) -> dict:
    """Process real payment via Method API"""
    try:
        # Create payment
        payment = method_client.payments.create({
            "amount": bill.amount_cents,
            "source": "your_bank_account_id",  # Your funding source
            "destination": "payee_account_id",  # Payee's account
            "description": f"Bill payment: {bill.subject}",
            "metadata": {
                "bill_id": bill.id,
                "payee": bill.payee
            }
        })
        
        return {
            "success": True,
            "payment_id": payment.id,
            "status": payment.status,
            "reference": payment.id
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

# Update reply logic
payment_result = await process_real_payment(bill)
if payment_result["success"]:
    reply_text = f"""Payment of {amount_str} has been processed.
Reference: {payment_result["reference"]}
Status: {payment_result["status"]}"""
else:
    reply_text = f"""Payment failed: {payment_result["error"]}
Please contact support."""
```

### 6. Add Payment Status Tracking

**Add to Bill model:**
```python
class Bill(Base):
    # ... existing fields ...
    method_payment_id = Column(String, nullable=True)
    payment_status = Column(String, nullable=True)  # pending, completed, failed
```

### 7. Add Webhook for Payment Updates

**Add endpoint:**
```python
@app.post("/api/method/webhook")
async def method_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle Method payment status updates"""
    payload = await request.json()
    
    event_type = payload.get("type")
    payment_data = payload.get("data", {})
    payment_id = payment_data.get("id")
    
    if event_type == "payment.completed":
        # Update bill status
        bill = db.query(Bill).filter(Bill.method_payment_id == payment_id).first()
        if bill:
            bill.payment_status = "completed"
            db.commit()
            
            # Notify user of successful payment
            await send_payment_confirmation(bill, db)
    
    return {"status": "processed"}
```

## Demo vs Production Differences

### Demo Mode (Current)
- ✅ Instant "payments" 
- ✅ No real money
- ✅ Perfect for demonstrations
- ✅ No bank account setup needed

### Production Mode (With Method)
- 🏦 Real bank transfers
- ⏱️ 1-3 business day processing
- 💰 Real money movement
- 🔐 Bank account verification required
- 📋 Compliance requirements

## Recommended Approach

1. **Demo First**: Use current DRYRUN system for demos
2. **Pilot**: Integrate Method with small amounts ($1-5)
3. **Scale**: Gradually increase limits
4. **Monitor**: Track success rates and failures

## Method API Resources

- [Method Documentation](https://docs.method.fi/)
- [Python SDK](https://github.com/MethodFi/method-python)
- [Sandbox Environment](https://dashboard.method.fi/)

## Security Notes

- Store Method API keys securely
- Use webhook signature verification
- Implement proper error handling
- Log all payment attempts
- Set up monitoring and alerts

## Testing Strategy

1. **Unit Tests**: Mock Method API responses
2. **Integration Tests**: Use Method sandbox
3. **End-to-End**: Small real payments in staging
4. **Load Tests**: Handle multiple concurrent payments

This integration can be added after the demo is working perfectly!
