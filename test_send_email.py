#!/usr/bin/env python3
"""
Test script to send an email using AgentMail
"""
from agentmail import AgentMail
import os
from dotenv import load_dotenv
from datetime import datetime

def test_send_email():
    # Load environment variables
    load_dotenv()
    
    api_key = os.getenv("AGENTMAIL_API_KEY")
    demo_inbox_id = os.getenv("DEMO_INBOX_ID")
    demo_agent_to = os.getenv("DEMO_AGENT_TO")
    user_email = os.getenv("USER_EMAIL", "you@example.com")
    
    if not api_key:
        print("❌ AGENTMAIL_API_KEY not found in .env file")
        return False
    
    if not demo_inbox_id:
        print("❌ DEMO_INBOX_ID not found in .env file")
        return False
    
    if not demo_agent_to:
        print("❌ DEMO_AGENT_TO not found in .env file")
        return False
    
    print(f"✅ Found API key: {api_key[:8]}...")
    print(f"✅ Found inbox ID: {demo_inbox_id}")
    print(f"✅ Found agent email: {demo_agent_to}")
    
    try:
        # Initialize client
        client = AgentMail(api_key=api_key)
        print("✅ AgentMail client initialized")
        
        # Create test bill email content
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        subject = f"Test Bill Payment Request - {timestamp}"
        text_content = f"""
Hello AgentPay!

This is a test bill for processing:

Bill Details:
- Payee: Electric Company
- Amount: $125.50
- Due Date: 2025-10-15
- Account Number: 12345678

Please process this payment at your earliest convenience.

Sent at: {timestamp}

Best regards,
Test User
        """.strip()
        
        html_content = f"""
<html>
<body>
    <h2>Test Bill Payment Request</h2>
    <p>Hello AgentPay!</p>
    
    <p>This is a test bill for processing:</p>
    
    <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 10px 0;">
        <h3>Bill Details:</h3>
        <ul>
            <li><strong>Payee:</strong> Electric Company</li>
            <li><strong>Amount:</strong> $125.50</li>
            <li><strong>Due Date:</strong> 2025-10-15</li>
            <li><strong>Account Number:</strong> 12345678</li>
        </ul>
    </div>
    
    <p>Please process this payment at your earliest convenience.</p>
    
    <p><small>Sent at: {timestamp}</small></p>
    
    <p>Best regards,<br>Test User</p>
</body>
</html>
        """.strip()
        
        print(f"\n📧 Sending test bill email...")
        print(f"   From inbox: {demo_inbox_id}")
        print(f"   To: {demo_agent_to}")
        print(f"   Subject: {subject}")
        
        # Send the email
        result = client.inboxes.messages.send(
            inbox_id=demo_inbox_id,
            to=demo_agent_to,
            subject=subject,
            text=text_content,
            html=html_content,
            labels=["test", "bill", "agentpay"]
        )
        
        print(f"✅ Email sent successfully!")
        print(f"   Message ID: {result.message_id}")
        print(f"   Status: {getattr(result, 'status', 'Unknown')}")
        
        # Try to get messages to verify
        print(f"\n📬 Checking inbox for messages...")
        messages = client.inboxes.messages.list(inbox_id=demo_inbox_id)
        print(f"✅ Found {messages.count} total messages in inbox")
        
        if messages.count > 0:
            print("\n📋 Most recent messages:")
            for i, msg in enumerate(messages.messages[:3]):
                print(f"  {i+1}. From: {getattr(msg, 'from_', 'Unknown')} | Subject: {getattr(msg, 'subject', 'No subject')}")
        
        print("\n🎉 Email sending test PASSED!")
        print(f"\n💡 You can now check your inbox at: {demo_agent_to}")
        print(f"💡 Or view messages via AgentMail dashboard for inbox: {demo_inbox_id}")
        
        return True
        
    except Exception as e:
        print(f"❌ Email sending test FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("📧 Testing AgentMail Email Sending...")
    print("=" * 60)
    success = test_send_email()
    exit(0 if success else 1)
