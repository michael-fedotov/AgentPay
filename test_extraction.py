#!/usr/bin/env python3
"""
Test script for bill extraction functionality
"""
import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import parse_amount_cents, parse_due_date_iso, regex_fallback, llm_extract
from dotenv import load_dotenv

def test_regex_functions():
    """Test individual regex functions"""
    print("🧪 Testing regex extraction functions...")
    print("=" * 50)
    
    # Test amount parsing
    print("\n💰 Testing amount parsing:")
    test_amounts = [
        "Amount due: $125.50",
        "Total Due $1,250.00",
        "Minimum due: 45.75",
        "Your balance: $2,500.25",
        "Pay $99.99 by Oct 15"
    ]
    
    for text in test_amounts:
        amount = parse_amount_cents(text)
        print(f"  '{text}' → {amount} cents")
    
    # Test date parsing
    print("\n📅 Testing date parsing:")
    test_dates = [
        "Due date: 2025-10-15",
        "Payment due 10/15/2025",
        "Pay by Oct 15, 2025",
        "Due: October 5, 2025",
        "Your bill is due on 12/25/2025"
    ]
    
    for text in test_dates:
        date = parse_due_date_iso(text)
        print(f"  '{text}' → {date}")

def test_full_extraction():
    """Test full bill extraction"""
    print("\n📧 Testing full bill extraction...")
    print("=" * 50)
    
    # Test email samples
    test_emails = [
        """
From: Electric Company <billing@electric-co.com>
Subject: Your Electric Bill is Ready

Dear Customer,

Your monthly electric bill is now available.

Account Number: 123456789
Amount Due: $125.50
Due Date: October 15, 2025

Please pay by the due date to avoid late fees.

Thank you,
Electric Company
        """,
        """
From: Credit Card Services <statements@chase.com>
Subject: Chase Credit Card Statement

Your Chase credit card statement is ready.

Total Due: $1,250.00
Minimum Payment Due: $45.00
Due Date: 11/01/2025

Account ending in 4567
        """,
        """
From: Comcast Internet <noreply@comcast.com>
Subject: Comcast Internet Bill

Internet Service Bill

Monthly charge: $89.99
Due: 2025-10-20

Thank you for being a Comcast customer.
        """
    ]
    
    for i, email in enumerate(test_emails, 1):
        print(f"\n📋 Test Email {i}:")
        result = regex_fallback(email.strip())
        print(f"  Payee: {result['payee']}")
        print(f"  Amount: {result['amount_cents']} cents")
        print(f"  Due Date: {result['due_date_iso']}")

async def test_llm_extraction():
    """Test LLM-based extraction"""
    print("\n🤖 Testing LLM extraction...")
    print("=" * 50)
    
    # Load environment to check if Gemini is configured
    load_dotenv()
    gemini_key = os.getenv("GEMINI_API_KEY")
    
    if not gemini_key:
        print("⚠️ GEMINI_API_KEY not set, LLM extraction will fall back to regex")
    else:
        print(f"✅ Found Gemini API key: {gemini_key[:10]}...")
    
    test_email = """
From: Electric Power Company <billing@epc.com>
Subject: Your Monthly Electric Bill

Dear Valued Customer,

Your electric service bill for September 2025 is now ready.

Account Details:
- Account Number: EPC-789456123
- Service Address: 123 Main St, Anytown, USA
- Billing Period: Sep 1 - Sep 30, 2025

Billing Summary:
- Previous Balance: $0.00
- Current Charges: $156.75
- Total Amount Due: $156.75
- Due Date: October 20, 2025

Please pay by the due date to avoid a $5.00 late fee.

Payment Options:
- Online: www.epc.com/pay
- Phone: 1-800-EPC-BILL
- Mail: PO Box 12345, Billing Dept

Thank you for choosing Electric Power Company!
    """
    
    print("\n📧 Testing with sample electric bill:")
    try:
        result = await llm_extract(test_email.strip())
        print(f"  Payee: {result['payee']}")
        print(f"  Amount: {result['amount_cents']} cents (${result['amount_cents']/100:.2f})" if result['amount_cents'] else "  Amount: None")
        print(f"  Due Date: {result['due_date_iso']}")
    except Exception as e:
        print(f"  ❌ Error: {e}")

async def main():
    """Run all tests"""
    print("🔧 AgentPay Bill Extraction Tests")
    print("=" * 60)
    
    # Test regex functions
    test_regex_functions()
    
    # Test full regex extraction
    test_full_extraction()
    
    # Test LLM extraction
    await test_llm_extraction()
    
    print("\n✅ All tests completed!")

if __name__ == "__main__":
    asyncio.run(main())
