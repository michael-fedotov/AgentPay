#!/usr/bin/env python3
"""
Process all unprocessed emails in the AgentMail inbox
This is useful for processing emails that arrived before webhook was set up
"""
import asyncio
import requests
import json
import sys
import os
from datetime import datetime

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app import agentmail_get_messages, settings

def get_processed_message_ids():
    """Get list of message IDs that have already been processed"""
    try:
        # This would normally query the database, but for now we'll use a simple approach
        # You could enhance this to check the database for existing bills
        return set()
    except:
        return set()

def trigger_webhook_for_message(message):
    """Trigger webhook processing for a specific message"""
    webhook_payload = {
        "type": "message.received",
        "data": {
            "inbox_id": message.inbox_id,
            "message_id": message.message_id,
            "from": getattr(message, 'from_', 'unknown@example.com'),
            "subject": getattr(message, 'subject', 'No Subject'),
            "timestamp": getattr(message, 'timestamp', datetime.utcnow()).isoformat() + "Z",
            "preview": getattr(message, 'preview', '')
        }
    }
    
    try:
        response = requests.post(
            "http://localhost:8000/webhook/agentmail",
            json=webhook_payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            return True, result
        else:
            return False, f"HTTP {response.status_code}: {response.text}"
    except Exception as e:
        return False, str(e)

def is_bill_like(message):
    """Simple heuristic to determine if a message looks like a bill"""
    subject = getattr(message, 'subject', '').lower()
    preview = getattr(message, 'preview', '').lower()
    from_email = getattr(message, 'from_', '').lower()
    
    # Skip messages from AgentMail itself (confirmations, etc.)
    if 'agentmail.to' in from_email:
        return False
    
    # Look for bill-like keywords
    bill_keywords = [
        'bill', 'invoice', 'statement', 'payment', 'due', 'amount',
        'electric', 'gas', 'water', 'phone', 'internet', 'credit card',
        'utility', 'wireless', 'cable', 'insurance', 'mortgage'
    ]
    
    text_to_check = f"{subject} {preview}".lower()
    return any(keyword in text_to_check for keyword in bill_keywords)

async def process_inbox():
    """Process all unprocessed messages in the inbox"""
    print("📧 Processing AgentMail Inbox")
    print("=" * 50)
    
    # Get messages from inbox
    print("📬 Fetching messages from AgentMail...")
    messages_result = agentmail_get_messages(settings.demo_inbox_id)
    
    if not messages_result["success"]:
        print(f"❌ Failed to fetch messages: {messages_result.get('error')}")
        return
    
    messages = messages_result["messages"]
    print(f"✅ Found {len(messages)} total messages")
    
    # Get already processed messages
    processed_ids = get_processed_message_ids()
    
    # Filter for unprocessed, bill-like messages
    unprocessed_bills = []
    for message in messages:
        if message.message_id not in processed_ids and is_bill_like(message):
            unprocessed_bills.append(message)
    
    print(f"🔍 Found {len(unprocessed_bills)} unprocessed bill-like messages")
    
    if not unprocessed_bills:
        print("✅ No unprocessed bills found!")
        return
    
    # Process each bill
    processed_count = 0
    failed_count = 0
    
    for i, message in enumerate(unprocessed_bills, 1):
        print(f"\n📋 Processing {i}/{len(unprocessed_bills)}: {getattr(message, 'subject', 'No Subject')}")
        print(f"   From: {getattr(message, 'from_', 'Unknown')}")
        print(f"   Date: {getattr(message, 'timestamp', 'Unknown')}")
        
        success, result = trigger_webhook_for_message(message)
        
        if success:
            if result.get('result', {}).get('bill_detected'):
                bill_result = result['result']
                print(f"   ✅ Bill processed successfully!")
                print(f"      Bill ID: {bill_result.get('bill_id')}")
                print(f"      Amount: ${bill_result.get('amount_cents', 0)/100:.2f}")
                print(f"      Payee: {bill_result.get('payee', 'Unknown')}")
                print(f"      Payment: {'✅ Processed' if bill_result.get('payment_processed') else '❌ Failed'}")
                processed_count += 1
            else:
                print(f"   ⚠️ Not identified as a bill")
        else:
            print(f"   ❌ Processing failed: {result}")
            failed_count += 1
        
        # Small delay between requests
        await asyncio.sleep(1)
    
    # Summary
    print(f"\n📊 Processing Summary")
    print("=" * 30)
    print(f"✅ Successfully processed: {processed_count}")
    print(f"❌ Failed to process: {failed_count}")
    print(f"⚠️ Not identified as bills: {len(unprocessed_bills) - processed_count - failed_count}")
    
    if processed_count > 0:
        print(f"\n🎉 {processed_count} bills have been processed and payments scheduled!")
        print(f"📧 Check your email for confirmation messages")

def main():
    """Main function"""
    print("🔄 AgentPay Inbox Processor")
    print("=" * 60)
    print("This tool processes all unprocessed bills in your AgentMail inbox")
    print("=" * 60)
    
    # Check if server is running
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code != 200:
            print("❌ AgentPay server is not responding")
            print("💡 Please start the server: uvicorn app:app --reload --port 8000")
            return
    except:
        print("❌ Cannot connect to AgentPay server")
        print("💡 Please start the server: uvicorn app:app --reload --port 8000")
        return
    
    print("✅ AgentPay server is running")
    
    # Process the inbox
    asyncio.run(process_inbox())

if __name__ == "__main__":
    main()
