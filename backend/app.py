from fastapi import FastAPI, UploadFile, File
import torch
from transformers import DetrImageProcessor, DetrForObjectDetection
from PIL import Image
import io
import pandas as pd
import random

app = FastAPI(title="X-Ray Security & Traveler Screening API")

# 1. Load AI Model
MODEL_NAME = "NabilaLM/detr-weapons-detection"
processor = DetrImageProcessor.from_pretrained(MODEL_NAME)
model = DetrForObjectDetection.from_pretrained(MODEL_NAME)

# 2. Load Traveler Records
# Ensure records-db.csv is in the same directory as app.py
try:
    traveler_db = pd.read_csv("records-db.csv")
    print(f"✅ Loaded {len(traveler_db)} traveler records.")
except Exception as e:
    print(f"❌ Error loading records-db.csv: {e}")
    traveler_db = pd.DataFrame()

def determine_security_action(weapon_found, prior_arrests, has_warrant):
    """Correlation logic based on background and scan results"""
    if weapon_found and has_warrant:
        return "ARREST: Prohibited item detected and subject has active warrant."
    elif weapon_found:
        return "DETAIN: Prohibited item detected. Hold for law enforcement."
    elif has_warrant:
        return "DETAIN: Active warrant detected for subject."
    elif prior_arrests > 0:
        return "SEARCH: No weapon found, but background warrants high-intensity manual search."
    else:
        return "PASS: No scanning or background threats found."

@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    # --- AI Scan Logic ---
    image_bytes = await file.read()
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    
    inputs = processor(images=image, return_tensors="pt")
    with torch.no_grad():
        outputs = model(**inputs)
    
    target_sizes = torch.tensor([image.size[::-1]])
    results = processor.post_process_object_detection(outputs, target_sizes=target_sizes, threshold=0.75)[0]
    
    detections = []
    weapon_detected = False
    for score, label, box in zip(results["scores"], results["labels"], results["boxes"]):
        label_name = model.config.id2label[label.item()]
        is_weapon = label_name in ['gun', 'pistol', 'weapon', 'LABEL_1']
        if is_weapon: weapon_detected = True
        
        detections.append({
            "label": "WEAPON" if is_weapon else label_name,
            "confidence": round(float(score), 4),
            "box": [round(i, 2) for i in box.tolist()]
        })

    # --- Record Correlation Logic ---
    # Pick a random traveler for simulation purposes
    record = traveler_db.sample(n=1).iloc[0].to_dict()
    
    # Process Recommendation
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
