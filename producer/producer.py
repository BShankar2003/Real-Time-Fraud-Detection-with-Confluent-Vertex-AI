import time
import random
import json
import os
from pathlib import Path
from confluent_kafka import Producer
from dotenv import load_dotenv

# Load .env from project root
env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=env_path)

# Producer config (JSON format - simpler than Avro)
producer_conf = {
    "bootstrap.servers": os.getenv("KAFKA_BOOTSTRAP"),
    "security.protocol": "SASL_SSL",
    "sasl.mechanisms": "PLAIN",
    "sasl.username": os.getenv("KAFKA_API_KEY"),
    "sasl.password": os.getenv("KAFKA_API_SECRET"),
    # Performance tuning
    "compression.type": "lz4",
    "linger.ms": 10,
    "batch.size": 32768,
}

producer = Producer(producer_conf)

def delivery_callback(err, msg):
    """Callback for message delivery confirmation"""
    if err:
        print(f"❌ Delivery failed: {err}")
    else:
        if msg.offset() % 100 == 0:  # Print every 100 messages
            print(f"✅ Delivered to {msg.topic()} [{msg.partition()}] @ offset {msg.offset()}")

def generate_transaction():
    """Generate realistic transaction with fraud patterns"""
    user_id = f"USER{random.randint(1, 50)}"
    
    # 5% chance of fraud pattern
    is_fraud = random.random() < 0.05
    
    if is_fraud:
        # Fraud pattern: high amount or rapid transactions
        amount = round(random.uniform(40000, 60000), 2)
    else:
        # Normal transaction
        amount = round(random.uniform(10, 5000), 2)
    
    return {
        "transaction_id": f"TXN{random.randint(100000, 999999)}",
        "user_id": user_id,
        "merchant_id": f"MERCHANT{random.randint(1, 20)}",
        "amount": amount,
        "timestamp": int(time.time() * 1000)  # Unix timestamp in milliseconds
    }

print("🚀 JSON Producer started (500 TPS target)")
print("=" * 70)

count = 0
start_time = time.time()

try:
    while True:
        txn = generate_transaction()
        
        # Produce as JSON (CHANGED: raw_transactions → raw_transactions)
        producer.produce(
            topic="raw_transactions",  # ✅ FIXED: underscore not hyphen
            key=txn["user_id"].encode('utf-8'),
            value=json.dumps(txn).encode('utf-8'),
            callback=delivery_callback
        )
        
        # Poll for delivery reports
        producer.poll(0)
        
        count += 1
        
        # Print statistics every 500 transactions
        if count % 500 == 0:
            elapsed = time.time() - start_time
            tps = count / elapsed if elapsed > 0 else 0
            print(f"📊 Sent: {count} transactions | TPS: {tps:.1f}")
        
        # Sleep to achieve ~500 TPS (0.002 seconds = 2ms)
        time.sleep(0.002)

except KeyboardInterrupt:
    print("\n⏹️  Stopping producer...")
finally:
    # Flush remaining messages
    producer.flush(10)
    elapsed = time.time() - start_time
    print(f"📊 Final: {count} transactions in {elapsed:.1f}s | Avg TPS: {count/elapsed:.1f}")