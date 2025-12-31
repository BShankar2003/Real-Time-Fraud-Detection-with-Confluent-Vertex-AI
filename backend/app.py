"""
Enhanced FastAPI backend for fraud detection dashboard
with AI model tracking and health monitoring
"""
import os
import json
import asyncio
import time
from collections import deque
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from confluent_kafka import Consumer
from dotenv import load_dotenv
from pathlib import Path

# Load environment
env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=env_path)

app = FastAPI(title="Fraud Detection API", version="1.0.0")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Track start time for uptime
start_time = time.time()

# In-memory storage with AI model tracking
stats = {
    "total": 0,
    "fraud": 0,
    "approved": 0,
    "review": 0,
    "fraud_rate": 0.0,
    "gemini_predictions": 0,  # NEW: Track Gemini usage
    "rule_predictions": 0     # NEW: Track rule-based usage
}
recent_transactions = deque(maxlen=50)

# Kafka consumer
consumer_conf = {
    "bootstrap.servers": os.getenv("KAFKA_BOOTSTRAP"),
    "security.protocol": "SASL_SSL",
    "sasl.mechanisms": "PLAIN",
    "sasl.username": os.getenv("KAFKA_API_KEY"),
    "sasl.password": os.getenv("KAFKA_API_SECRET"),
    "group.id": "dashboard-consumer",
    "auto.offset.reset": "latest",
}

consumer = Consumer(consumer_conf)
consumer.subscribe(["fraud_predictions"])

# Background task to consume messages
async def consume_messages():
    while True:
        msg = consumer.poll(0.1)
        if msg and not msg.error():
            try:
                data = json.loads(msg.value().decode("utf-8"))
                
                # Update stats
                stats["total"] += 1
                decision = data.get("decision", "")
                if decision == "BLOCKED":
                    stats["fraud"] += 1
                elif decision == "APPROVED":
                    stats["approved"] += 1
                elif decision == "REVIEW":
                    stats["review"] += 1
                
                # Track which model made the prediction
                model = data.get("model", "unknown")
                if model == "gemini-2.0-flash":
                    stats["gemini_predictions"] += 1
                elif model == "rule-based":
                    stats["rule_predictions"] += 1
                
                # Calculate fraud rate
                if stats["total"] > 0:
                    stats["fraud_rate"] = (stats["fraud"] / stats["total"]) * 100
                
                # Add to recent transactions
                recent_transactions.append(data)
                
            except Exception as e:
                print(f"❌ Error processing message: {e}")
        
        await asyncio.sleep(0.01)

@app.on_event("startup")
async def startup():
    """Start background message consumer"""
    print("🚀 Starting Fraud Detection API...")
    print("=" * 70)
    asyncio.create_task(consume_messages())
    print("✅ Dashboard backend running on http://127.0.0.1:8000")

@app.get("/")
def root():
    """API root endpoint"""
    return {
        "status": "running",
        "service": "Fraud Detection API",
        "version": "1.0.0",
        "endpoints": {
            "stats": "/api/stats",
            "health": "/api/health",
            "recent": "/api/transactions/recent",
            "websocket": "/ws/transactions"
        }
    }

@app.get("/api/health")
def health_check():
    """Health check endpoint with system status"""
    uptime_seconds = int(time.time() - start_time)
    uptime_minutes = uptime_seconds // 60
    uptime_hours = uptime_minutes // 60
    
    return {
        "status": "healthy",
        "kafka_connected": True,
        "total_processed": stats["total"],
        "gemini_enabled": stats["gemini_predictions"] > 0,
        "uptime": {
            "seconds": uptime_seconds,
            "formatted": f"{uptime_hours}h {uptime_minutes % 60}m {uptime_seconds % 60}s"
        },
        "ai_models": {
            "gemini": stats["gemini_predictions"],
            "rules": stats["rule_predictions"]
        }
    }

@app.get("/api/stats")
def get_stats():
    """Get current fraud detection statistics"""
    return stats

@app.get("/api/transactions/recent")
def get_recent(limit: int = 20):
    """Get recent transactions"""
    return {
        "transactions": list(recent_transactions)[-limit:],
        "count": len(recent_transactions)
    }

@app.websocket("/ws/transactions")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await websocket.accept()
    print("🔌 WebSocket client connected")
    
    try:
        while True:
            # Send current stats
            await websocket.send_json({
                "type": "stats",
                "data": stats
            })
            
            # Send recent transaction if available
            if recent_transactions:
                await websocket.send_json({
                    "type": "transaction",
                    "data": recent_transactions[-1]
                })
            
            await asyncio.sleep(1)
    except Exception as e:
        print(f"🔌 WebSocket disconnected: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host="127.0.0.1", 
        port=8000,
        log_level="info"
    )