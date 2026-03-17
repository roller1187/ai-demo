from fastapi import FastAPI, UploadFile, File
import torch
from transformers import DetrImageProcessor, DetrForObjectDetection
from PIL import Image
import io

app = FastAPI()

MODEL_NAME = "NabilaLM/detr-weapons-detection"
processor = DetrImageProcessor.from_pretrained(MODEL_NAME)
model = DetrForObjectDetection.from_pretrained(MODEL_NAME)

@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    image_bytes = await file.read()
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    
    inputs = processor(images=image, return_tensors="pt")
    with torch.no_grad():
        outputs = model(**inputs)
    
    target_sizes = torch.tensor([image.size[::-1]])
    results = processor.post_process_object_detection(outputs, target_sizes=target_sizes, threshold=0.75)[0]
    
    detections = []
    for score, label, box in zip(results["scores"], results["labels"], results["boxes"]):
        label_name = model.config.id2label[label.item()]
        detections.append({
            "label": "WEAPON" if label_name in ['gun', 'pistol', 'weapon', 'LABEL_1'] else label_name,
            "confidence": round(float(score), 4),
            "box": [round(i, 2) for i in box.tolist()] # [xmin, ymin, xmax, ymax]
        })
    
    return {"detections": detections}
