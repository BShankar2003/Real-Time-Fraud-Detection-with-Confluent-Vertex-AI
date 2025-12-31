# test_enriched_consumer.py
import os
import json
from confluent_kafka import Consumer
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=env_path)

consumer_conf = {
    "bootstrap.servers": os.getenv("KAFKA_BOOTSTRAP"),
    "security.protocol": "SASL_SSL",
    "sasl.mechanisms": "PLAIN",
    "sasl.username": os.getenv("KAFKA_API_KEY"),
    "sasl.password": os.getenv("KAFKA_API_SECRET"),
    "group.id": "debug-enriched-consumer",
    "auto.offset.reset": "latest",
}

consumer = Consumer(consumer_conf)
consumer.subscribe(["enriche_transactions"])

print("🔍 Reading from enriche_transactions topic...")
print("Waiting for messages with amount_category field...\n")

for i in range(5):
    msg = consumer.poll(5.0)
    if msg and not msg.error():
        data = json.loads(msg.value().decode("utf-8"))
        print(f"✅ Message {i+1}:")
        print(json.dumps(data, indent=2))
        
        # Check if amount_category exists
        if "amount_category" in data:
            print(f"✅ amount_category field found: {data['amount_category']}")
        else:
            print("⚠️ amount_category field missing!")
        
        print("\n" + "="*50 + "\n")
    else:
        print(f"⏳ Waiting... (attempt {i+1}/5)")

consumer.close()
print("\n✅ Test complete!")