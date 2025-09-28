#!/usr/bin/env python3
"""
Quick email processing script for AgentPay
Use this to manually process the latest emails in your inbox
"""
import requests
import json
import sys
import os
from datetime import datetime

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app import agentmail_get_messages, settings

def process_latest_email():
    """Process the most recent email in the inbox"""
    print("📧 Processing Latest Email from AgentMail")
    print("=" * 50)
    
    # Get messages
    messages_result = agentmail_get_messages(settings.demo_inbox_id)
    if not messages_result["success"]:
        print(f"❌ Failed to fetch messages: {messages_result.get('error')}")
        return
    
    messages = messages_result["messages"]
    if not messages:
        print("📭 No messages found in inbox")
        return
    
    # Get the latest message
    latest_message = messages[0]
    
    print(f"📋 Latest Message:")
    print(f"   From: {getattr(latest_message, 'from_', 'Unknown')}")
    print(f"   Subject: {getattr(latest_message, 'subject', 'No Subject')}")
    print(f"   Date: {getattr(latest_message, 'timestamp', 'Unknown')}")
    print(f"   Message ID: {latest_message.message_id}")
    
    # Ask user if they want to process it
    response = input(f"\n🤔 Process this email as a bill? (y/n): ").lower().strip()
    
    if response != 'y':
        print("⏭️ Skipping processing")
        return
    
    # Create webhook payload
    webhook_payload = {
        "type": "message.received",
        "data": {
            "inbox_id": latest_message.inbox_id,
            "message_id": latest_message.message_id,
            "from": getattr(latest_message, 'from_', 'unknown@example.com'),
            "subject": getattr(latest_message, 'subject', 'No Subject'),
            "timestamp": getattr(latest_message, 'timestamp', datetime.utcnow()).isoformat() + "Z"
        }
    }
    
    print(f"\n🔄 Processing email...")
    
    # Send to webhook
    try:
        response = requests.post(
            "http://localhost:8000/webhook/agentmail",
            json=webhook_payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Processing completed!")
            
            if result.get('result', {}).get('success'):
                webhook_result = result['result']
                
                if webhook_result.get('bill_detected'):
                    print(f"\n🎉 Bill Successfully Processed:")
                    print(f"   📋 Bill ID: {webhook_result.get('bill_id')}")
                    print(f"   🏢 Payee: {webhook_result.get('payee', 'Unknown')}")
                    print(f"   💰 Amount: ${webhook_result.get('amount_cents', 0)/100:.2f}")
                    print(f"   📅 Due Date: {webhook_result.get('due_date', 'Unknown')}")
                    print(f"   💳 Payment: {'✅ Processed' if webhook_result.get('payment_processed') else '❌ Failed'}")
                    print(f"   📧 Confirmation: {'✅ Sent' if webhook_result.get('confirmation_sent') else '❌ Failed'}")
                else:
                    print(f"⚠️ Email was not identified as a bill")
                    print(f"   Reason: {webhook_result.get('message', 'Unknown')}")
            else:
                print(f"❌ Processing failed: {webhook_result.get('error', 'Unknown error')}")
        else:
            print(f"❌ Webhook request failed: {response.status_code}")
            print(f"   Response: {response.text}")
    
    except Exception as e:
        print(f"❌ Error processing email: {e}")

def show_recent_messages():
    """Show recent messages in the inbox"""
    print("📬 Recent Messages in AgentMail Inbox")
    print("=" * 50)
    
    messages_result = agentmail_get_messages(settings.demo_inbox_id)
    if not messages_result["success"]:
        print(f"❌ Failed to fetch messages: {messages_result.get('error')}")
        return
    
    messages = messages_result["messages"]
    print(f"📊 Total messages: {len(messages)}")
    
    print(f"\n📋 Recent Messages:")
    for i, message in enumerate(messages[:5], 1):
        from_email = getattr(message, 'from_', 'Unknown')
        subject = getattr(message, 'subject', 'No Subject')
        timestamp = getattr(message, 'timestamp', 'Unknown')
        
        # Truncate long subjects
        if len(subject) > 50:
            subject = subject[:47] + "..."
        
        print(f"   {i}. {from_email}")
        print(f"      📧 {subject}")
        print(f"      🕒 {timestamp}")
        print()

def main():
    """Main function"""
    print("⚡ AgentPay Quick Email Processor")
    print("=" * 60)
    
    # Check server
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code != 200:
            print("❌ AgentPay server is not responding")
            return
    except:
        print("❌ Cannot connect to AgentPay server")
        print("💡 Start server: uvicorn app:app --reload --port 8000")
        return
    
    print("✅ AgentPay server is running")
    
    while True:
        print(f"\n🎯 What would you like to do?")
        print(f"1. Process latest email")
        print(f"2. Show recent messages")
        print(f"3. Exit")
        
        choice = input(f"\nEnter choice (1-3): ").strip()
        
        if choice == '1':
            process_latest_email()
        elif choice == '2':
            show_recent_messages()
        elif choice == '3':
            print("👋 Goodbye!")
            break
        else:
            print("❌ Invalid choice. Please enter 1, 2, or 3.")

if __name__ == "__main__":
    main()
