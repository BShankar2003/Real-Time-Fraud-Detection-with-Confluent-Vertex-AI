import json
import os
from confluent_kafka import Consumer, Producer
from dotenv import load_dotenv
from pathlib import Path
from collections import defaultdict
import vertexai
from vertexai.generative_models import GenerativeModel

env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=env_path)

# Initialize Vertex AI (uses gcloud auth automatically)
PROJECT_ID = os.getenv("GCP_PROJECT_ID", "project-53a73f94-a208-4988-908")
LOCATION = os.getenv("GCP_REGION", "us-central1")

print("🤖 Initializing Gemini AI...")
try:
    vertexai.init(project=PROJECT_ID, location=LOCATION)
    gemini_model = GenerativeModel("gemini-2.0-flash-exp")
    print("✅ Gemini AI initialized successfully!")
except Exception as e:
    print(f"❌ Gemini initialization failed: {e}")
    print("⚠️  Falling back to rule-based detection")
    gemini_model = None

# Kafka consumer config
consumer_conf = {
    "bootstrap.servers": os.getenv("KAFKA_BOOTSTRAP"),
    "security.protocol": "SASL_SSL",
    "sasl.mechanisms": "PLAIN",
    "sasl.username": os.getenv("KAFKA_API_KEY"),
    "sasl.password": os.getenv("KAFKA_API_SECRET"),
    "group.id": "fraud-detector-group",
    "auto.offset.reset": "latest",
}

consumer = Consumer(consumer_conf)
consumer.subscribe(["enriched_transactions"])

producer_conf = {
    "bootstrap.servers": os.getenv("KAFKA_BOOTSTRAP"),
    "security.protocol": "SASL_SSL",
    "sasl.mechanisms": "PLAIN",
    "sasl.username": os.getenv("KAFKA_API_KEY"),
    "sasl.password": os.getenv("KAFKA_API_SECRET"),
}

producer = Producer(producer_conf)

print("🚨 Fraud Detector Started (Powered by Gemini AI)")
print("=" * 70)

# Track user velocity
user_txns = defaultdict(list)
WINDOW_SEC = 60

processed = 0
fraud_count = 0
gemini_count = 0
rule_based_count = 0

def predict_fraud_with_gemini(data, txn_count, total_amount):
    """Use Gemini AI to classify fraud"""
    try:
        prompt = f"""You are an expert fraud detection system. Analyze this transaction and respond ONLY with a JSON object.

Transaction Details:
- Amount: ₹{data['amount']:,.2f}
- User: {data['user_id']}
- Merchant: {data['merchant_id']}
- Transactions in last minute: {txn_count}
- Total amount in last minute: ₹{total_amount:,.2f}
- Amount category: {data.get('amount_category', 'UNKNOWN')}

Known Fraud Patterns:
1. High amounts (>₹50,000) = suspicious
2. Rapid transactions (>5 in 1 minute) = velocity attack
3. Large cumulative amounts (>₹100,000 in 1 min) = suspicious

Respond with ONLY this JSON format (no markdown, no explanation):
{{"fraud_score": 0.85, "decision": "BLOCKED", "reasoning": "High amount with rapid velocity"}}

Decision rules:
- fraud_score >= 0.7 → decision: "BLOCKED"
- fraud_score 0.4-0.69 → decision: "REVIEW"
- fraud_score < 0.4 → decision: "APPROVED"
"""
        
        response = gemini_model.generate_content(
            prompt,
            generation_config={
                "temperature": 0.1,
                "max_output_tokens": 200,
            }
        )
        
        response_text = response.text.strip()
        
        # Clean up response
        if '```json' in response_text:
            response_text = response_text.split('```json')[1].split('```')[0].strip()
        elif '```' in response_text:
            response_text = response_text.split('```')[1].split('```')[0].strip()
        
        result = json.loads(response_text)
        
        return {
            "fraud_score": result.get("fraud_score", 0.5),
            "decision": result.get("decision", "REVIEW"),
            "reasoning": result.get("reasoning", "AI analysis"),
            "model": "gemini-2.0-flash"
        }
        
    except Exception as e:
        print(f"⚠️  Gemini prediction failed: {e}")
        return None

def predict_fraud_rule_based(data, txn_count, total_amount):
    """Fallback rule-based fraud detection"""
    amount = data['amount']
    fraud_score = 0.0
    reasons = []
    
    if amount > 50000:
        fraud_score += 0.5
        reasons.append(f"High amount: ₹{amount:,.0f}")
    
    if txn_count >= 10:
        fraud_score += 0.6
        reasons.append(f"High velocity: {txn_count} txns/min")
    elif txn_count >= 5:
        fraud_score += 0.4
        reasons.append(f"Moderate velocity: {txn_count} txns/min")
    
    if total_amount > 100000:
        fraud_score += 0.3
        reasons.append(f"High window: ₹{total_amount:,.0f}")
    
    if fraud_score >= 0.7:
        decision = "BLOCKED"
    elif fraud_score >= 0.4:
        decision = "REVIEW"
    else:
        decision = "APPROVED"
    
    return {
        "fraud_score": fraud_score,
        "decision": decision,
        "reasoning": ", ".join(reasons) if reasons else "Normal pattern",
        "model": "rule-based"
    }

try:
    while True:
        msg = consumer.poll(1.0)
        
        if msg is None:
            continue
        
        if msg.error():
            continue
        
        try:
            # Handle Schema Registry format (5-byte header)
            raw_value = msg.value()
            
            # Check if this is Schema Registry format (starts with magic byte 0x00)
            if len(raw_value) > 5 and raw_value[0] == 0:
                # Skip first 5 bytes (magic byte + 4-byte schema ID)
                json_data = raw_value[5:]
            else:
                # Plain JSON format
                json_data = raw_value
            
            # Decode to JSON
            data = json.loads(json_data.decode("utf-8"))
            
            user_id = data["user_id"]
            amount = data["amount"]
            timestamp = data["timestamp"] / 1000
            
            # Track velocity
            user_txns[user_id].append({"amount": amount, "time": timestamp})
            user_txns[user_id] = [t for t in user_txns[user_id] if (timestamp - t["time"]) <= WINDOW_SEC]
            
            txn_count = len(user_txns[user_id])
            total_amount = sum(t["amount"] for t in user_txns[user_id])
            
            # Try Gemini first, fallback to rules
            if gemini_model:
                prediction = predict_fraud_with_gemini(data, txn_count, total_amount)
                if prediction:
                    gemini_count += 1
                else:
                    prediction = predict_fraud_rule_based(data, txn_count, total_amount)
                    rule_based_count += 1
            else:
                prediction = predict_fraud_rule_based(data, txn_count, total_amount)
                rule_based_count += 1
            
            # Count fraud
            if prediction["decision"] == "BLOCKED":
                fraud_count += 1
            
            result = {
                "transaction_id": data["transaction_id"],
                "user_id": user_id,
                "amount": amount,
                "fraud_score": prediction["fraud_score"],
                "decision": prediction["decision"],
                "risk_level": "HIGH" if prediction["decision"] == "BLOCKED" else "MEDIUM" if prediction["decision"] == "REVIEW" else "LOW",
                "txn_count_1min": txn_count,
                "total_amount_1min": total_amount,
                "reasons": prediction["reasoning"],
                "model": prediction["model"]
            }
            
            producer.produce(
                topic="fraud_predictions",
                key=user_id.encode('utf-8'),
                value=json.dumps(result).encode('utf-8')
            )
            producer.poll(0)
            
            processed += 1
            
            if prediction["decision"] == "BLOCKED":
                model_emoji = "🤖" if prediction["model"] == "gemini-2.0-flash" else "📋"
                print(f"🚨 {model_emoji} FRAUD: {user_id} | ₹{amount:,.0f} | Score={prediction['fraud_score']:.2f}")
            
            if processed % 50 == 0:
                rate = (fraud_count/processed)*100
                print(f"📊 {processed} processed | {fraud_count} fraud ({rate:.1f}%) | Gemini: {gemini_count} | Rules: {rule_based_count}")
        
        except Exception as e:
            print(f"❌ Error: {e}")
            continue

except KeyboardInterrupt:
    print("\n⏹️  Stopping...")
finally:
    producer.flush()
    consumer.close()
    print(f"✅ Final: {processed} processed, {fraud_count} fraud")
    print(f"📊 Gemini predictions: {gemini_count}, Rule-based: {rule_based_count}")