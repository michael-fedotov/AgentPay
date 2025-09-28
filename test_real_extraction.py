#!/usr/bin/env python3
"""
Test bill extraction with real emails from AgentMail
"""
import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import llm_extract, agentmail_get_messages, agentmail_get_message, settings
from dotenv import load_dotenv

async def test_with_real_emails():
    """Test extraction with real emails from AgentMail"""
    print("📧 Testing bill extraction with real emails...")
    print("=" * 60)
    
    # Load environment
    load_dotenv()
    
    if not settings.agentmail_api_key or not settings.demo_inbox_id:
        print("❌ AgentMail credentials not configured")
        return
    
    print(f"✅ Using inbox: {settings.demo_inbox_id}")
    
    # Get messages from inbox
    print("\n📬 Fetching messages from AgentMail...")
    messages_result = agentmail_get_messages(settings.demo_inbox_id)
    
    if not messages_result["success"]:
        print(f"❌ Failed to fetch messages: {messages_result.get('error')}")
        return
    
    messages = messages_result["messages"]
    print(f"✅ Found {len(messages)} messages")
    
    # Test extraction on each message
    for i, message in enumerate(messages[:3]):  # Test first 3 messages
        print(f"\n📋 Message {i+1}:")
        print(f"  From: {getattr(message, 'from_', 'Unknown')}")
        print(f"  Subject: {getattr(message, 'subject', 'No subject')}")
        
        # Get full message content
        message_result = agentmail_get_message(settings.demo_inbox_id, message.message_id)
        
        if message_result["success"]:
            full_message = message_result["message"]
            
            # Combine text and HTML content for extraction
            email_text = ""
            if hasattr(full_message, 'text') and full_message.text:
                email_text += f"TEXT CONTENT:\n{full_message.text}\n\n"
            if hasattr(full_message, 'html') and full_message.html:
                email_text += f"HTML CONTENT:\n{full_message.html}\n\n"
            
            # Add headers for context
            email_text = f"From: {getattr(message, 'from_', 'Unknown')}\nSubject: {getattr(message, 'subject', 'No subject')}\n\n{email_text}"
            
            print(f"  Content length: {len(email_text)} characters")
            
            # Extract bill information
            try:
                result = await llm_extract(email_text)
                print(f"  🔍 Extraction result:")
                print(f"    Payee: {result.get('payee', 'None')}")
                print(f"    Amount: {result.get('amount_cents', 'None')} cents", end="")
                if result.get('amount_cents'):
                    print(f" (${result['amount_cents']/100:.2f})")
                else:
                    print()
                print(f"    Due Date: {result.get('due_date_iso', 'None')}")
                
                # Show if this looks like a bill
                is_bill = any([
                    result.get('amount_cents') is not None,
                    result.get('due_date_iso') is not None,
                    any(word in email_text.lower() for word in ['bill', 'due', 'payment', 'amount', 'invoice'])
                ])
                print(f"    📊 Looks like a bill: {'✅ Yes' if is_bill else '❌ No'}")
                
            except Exception as e:
                print(f"  ❌ Extraction failed: {e}")
        else:
            print(f"  ❌ Failed to get full message: {message_result.get('error')}")
    
    print(f"\n✅ Real email testing completed!")

async def test_send_and_extract():
    """Send a test bill email and then extract from it"""
    print("\n🚀 Testing send → extract workflow...")
    print("=" * 50)
    
    # Import send functionality
    from app import agentmail_send
    from datetime import datetime
    
    if not settings.demo_agent_to:
        print("❌ DEMO_AGENT_TO not configured")
        return
    
    # Create a realistic test bill
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    subject = f"Test Utility Bill - {timestamp}"
    
    bill_content = f"""
From: Metro Electric Company <billing@metroelectric.com>
Subject: Your Electric Bill is Ready - Account 789456123

Dear Valued Customer,

Your electric service bill for September 2025 is now available.

ACCOUNT INFORMATION:
Account Number: 789456123
Service Address: 456 Oak Street, Springfield, USA
Billing Period: September 1-30, 2025

BILLING SUMMARY:
Previous Balance: $0.00
Current Electric Charges: $187.25
Total Amount Due: $187.25
Due Date: October 30, 2025

USAGE DETAILS:
kWh Used: 875 kWh
Rate: $0.214 per kWh

Please pay by the due date to avoid a $15.00 late fee.

PAYMENT OPTIONS:
• Online: www.metroelectric.com/pay
• Phone: 1-800-METRO-55
• Mail: Metro Electric, PO Box 98765, Springfield, USA

Thank you for choosing Metro Electric Company!

Questions? Contact us at support@metroelectric.com or 1-800-METRO-55.

This is an automated message. Please do not reply to this email.
    """.strip()
    
    print(f"📧 Sending test bill email...")
    send_result = agentmail_send(
        inbox_id=settings.demo_inbox_id,
        to=settings.demo_agent_to,
        subject=subject,
        text=bill_content,
        labels=["test-bill", "extraction-test"]
    )
    
    if send_result["success"]:
        print(f"✅ Email sent! Message ID: {send_result['message_id']}")
        
        # Wait a moment for delivery
        print("⏳ Waiting 3 seconds for delivery...")
        await asyncio.sleep(3)
        
        # Now extract from the sent content
        print(f"🔍 Testing extraction on sent content...")
        result = await llm_extract(bill_content)
        
        print(f"📊 Extraction Results:")
        print(f"  Payee: {result.get('payee', 'None')}")
        print(f"  Amount: {result.get('amount_cents', 'None')} cents", end="")
        if result.get('amount_cents'):
            print(f" (${result['amount_cents']/100:.2f})")
        else:
            print()
        print(f"  Due Date: {result.get('due_date_iso', 'None')}")
        
        # Validate results
        expected_amount = 18725  # $187.25 in cents
        expected_date = "2025-10-30"
        
        print(f"\n✅ Validation:")
        print(f"  Amount correct: {'✅' if result.get('amount_cents') == expected_amount else '❌'} (expected {expected_amount})")
        print(f"  Date correct: {'✅' if result.get('due_date_iso') == expected_date else '❌'} (expected {expected_date})")
        print(f"  Payee found: {'✅' if result.get('payee') else '❌'}")
        
    else:
        print(f"❌ Failed to send email: {send_result.get('error')}")

async def main():
    """Run all tests"""
    print("🧪 AgentPay Real Email Extraction Tests")
    print("=" * 60)
    
    # Test with existing emails
    await test_with_real_emails()
    
    # Test send and extract workflow
    await test_send_and_extract()
    
    print(f"\n🎉 All real email tests completed!")

if __name__ == "__main__":
    asyncio.run(main())
