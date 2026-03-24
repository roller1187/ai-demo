from fastapi import FastAPI, UploadFile, File
import torch
from transformers import DetrImageProcessor, DetrForObjectDetection
from PIL import Image
import io
import pandas as pd
import random
import os

app = FastAPI(title="X-Ray Security & Traveler Screening API")

# 1. Load AI Model once on startup
MODEL_NAME = "NabilaLM/detr-weapons-detection"
processor = DetrImageProcessor.from_pretrained(MODEL_NAME)
model = DetrForObjectDetection.from_pretrained(MODEL_NAME)

# 2. Load Traveler Records
# Make sure records-db.csv is in the same directory or adjust path
csv_path = "records-db.csv"
try:
    if os.path.exists(csv_path):
        traveler_db = pd.read_csv(csv_path)
        print(f"✅ Loaded {len(traveler_db)} traveler records.")
    else:
        print(f"⚠️ {csv_path} not found. Correlation will fail.")
        traveler_db = pd.DataFrame()
except Exception as e:
    print(f"❌ Error loading records: {e}")
    traveler_db = pd.DataFrame()

def determine_security_action(weapon_found, prior_arrests, has_warrant):
    """Business logic for security escalation"""
    if weapon_found and has_warrant:
        return "CRITICAL ARREST: Weapon detected on subject with active warrant."
    elif weapon_found:
        return "LE DETAIN: Prohibited weapon detected. Notify law enforcement."
    elif has_warrant:
        return "DETAIN: Subject has an active warrant for arrest."
    elif prior_arrests > 0:
        return "INTENSIVE SEARCH: High-risk background. Perform manual bag search."
    else:
        return "PASS: No scanning or background threats found."

@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    # Read image from request
    contents = await file.read()
    image = Image.open(io.BytesIO(contents)).convert("RGB")
    
    # AI Inference
    inputs = processor(images=image, return_tensors="pt")
    with torch.no_grad():
        outputs = model(**inputs)
    
    # Process results
    target_sizes = torch.tensor([image.size[::-1]])
    results = processor.post_process_object_detection(outputs, target_sizes=target_sizes, threshold=0.75)[0]
    
    detections = []
    weapon_detected = False
    for score, label, box in zip(results["scores"], results["labels"], results["boxes"]):
        label_id = label.item()
        label_name = model.config.id2label[label_id]
        
        # Check if detected object is a weapon
        is_weapon = label_name in ['gun', 'pistol', 'weapon', 'LABEL_1']
        if is_weapon: weapon_detected = True
        
        detections.append({
            "label": "WEAPON" if is_weapon else label_name,
            "confidence": round(float(score), 4),
            "box": [round(i, 2) for i in box.tolist()] # [xmin, ymin, xmax, ymax]
        })

    # Pick a random traveler for simulation
    if not traveler_db.empty:
        record = traveler_db.sample(n=1).iloc[0].to_dict()
    else:
        record = {"Full Name": "Unknown", "Prior Arrests": 0, "Pending Warrants": "No"}
    
    # Logic Correlation
    recommendation = determine_security_action(
        weapon_found=weapon_detected,
        prior_arrests=int(record.get('Prior Arrests', 0)),
        has_warrant=str(record.get('Pending Warrants', 'No')).lower() == 'yes'
    )

    return {
        "traveler": {
            "name": record.get("Full Name"),
            "origin": record.get("Country of Origin"),
            "dob": record.get("Date of Birth"),
            "history": {
                "prior_arrests": int(record.get("Prior Arrests", 0)),
                "warrants": record.get("Pending Warrants"),
                "charges": record.get("List of Charges")
            }
        },
        "detections": detections,
        "recommendation": recommendation
    }

@app.get("/health")
def health():
    return {"status": "ready"}

if __name__ == "__main__":
    import uvicorn
    # This command starts the server and BLOCKS the script from exiting
    uvicorn.run(app, host="0.0.0.0", port=8080)
