from fastapi import FastAPI, UploadFile, File
import base64
import httpx
import io
import pandas as pd
import os

app = FastAPI(title="X-Ray Security & Traveler Screening API")

# 1. Remote DETR Model Service (configurable via env var)
MODEL_SERVICE_URL = os.environ.get(
    "MODEL_SERVICE_URL",
    "https://detr-weapons-detection-demo-models.apps.aromerot.redhat-openshift.com"
)
MODEL_NAME = os.environ.get("MODEL_NAME", "detr-weapons-detection")
PREDICT_URL = f"{MODEL_SERVICE_URL}/v1/models/{MODEL_NAME}:predict"

print(f"✅ Using remote model service: {PREDICT_URL}")

# 2. Load Traveler Records
csv_path = "records-db.csv"
try:
    if os.path.exists(csv_path):
        traveler_db = pd.read_csv(csv_path).fillna("")
        print(f"✅ Loaded {len(traveler_db)} traveler records.")
    else:
        print(f"⚠️ {csv_path} not found. Correlation will use dummy data.")
        traveler_db = pd.DataFrame()
except Exception as e:
    print(f"❌ Error loading records: {e}")
    traveler_db = pd.DataFrame()


def determine_security_action(weapon_found, prior_arrests, has_warrant):
    """Correlation logic for security recommendations"""
    if weapon_found and has_warrant:
        return "🚨 CRITICAL ARREST:\n Weapon detected on subject with active warrant.\n‼️EXTREME RISK‼️ Trap subject and notify law enforcement."
    elif weapon_found:
        return "⛔️ LAW ENFORCEMENT DETAIN:\nProhibited weapon detected.\n🚨 Notify law enforcement."
    elif has_warrant:
        return "✋ DETAIN:\n Subject has an active warrant for arrest.\n🚨 Notify law enforcement."
    elif prior_arrests > 0:
        return "⚠️ INTENSIVE SEARCH:\n High-risk background.\n🔎 Perform manual bag search."
    else:
        return "✅ PASS: No scanning or background threats found."


@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    # Read image from request
    contents = await file.read()

    # Encode image as base64 for KServe v1 API
    b64_image = base64.b64encode(contents).decode("utf-8")

    # Call remote DETR model service
    async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
        response = await client.post(
            PREDICT_URL,
            json={"instances": [b64_image]}
        )
        response.raise_for_status()
        model_response = response.json()

    # Process detections from model response
    detections = []
    weapon_detected = False

    predictions = model_response.get("predictions", [{}])
    if predictions:
        raw_detections = predictions[0].get("detections", [])
        for det in raw_detections:
            label_name = det.get("label", "unknown")
            confidence = det.get("confidence", 0.0)
            raw_box = det.get("box", [0, 0, 0, 0])
            if isinstance(raw_box, dict):
                box = [raw_box.get("xmin", 0), raw_box.get("ymin", 0),
                       raw_box.get("xmax", 0), raw_box.get("ymax", 0)]
            else:
                box = raw_box

            # Check if detected object is a weapon
            is_weapon = label_name.lower() in ['gun', 'pistol', 'weapon', 'label_1']
            if is_weapon:
                weapon_detected = True

            detections.append({
                "label": "WEAPON" if is_weapon else label_name,
                "confidence": round(float(confidence), 4),
                "box": [round(float(i), 2) for i in box]
            })

    # Criminal Record Database Correlation
    if not traveler_db.empty:
        record = traveler_db.sample(n=1).iloc[0].to_dict()
    else:
        record = {
            "Full Name": "Unknown Subject",
            "Prior Arrests": 0,
            "Pending Warrants": "No",
            "Country of Origin": "Unknown",
            "Date of Birth": "Unknown",
            "List of Charges": ""
        }

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


# The following starts the server and blocks the script from exiting
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
