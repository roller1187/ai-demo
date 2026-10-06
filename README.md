# TSA AI-Powered Security Screening System

An enterprise-grade demonstration application showcasing how **AI-powered computer vision** and **cross-agency data correlation** can transform Transportation Security Administration (TSA) checkpoint operations.

## Mission Statement

This solution is specifically designed for **Transportation Security Administration (TSA)** use cases to:

- **Enhance Airport Security**: Deploy AI-powered weapon detection on X-ray baggage imagery
- **Reduce Human Error**: Automate threat identification with confidence threshold detection
- **Enable Cross-Agency Correlation**: Integrate screening results with FBI criminal databases and warrant systems
- **Improve Decision Speed**: Provide instant security recommendations based on correlated threat + background data

## System Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                    TSA Security Checkpoint                        │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                   QUARKUS WEB INTERFACE                           │
│              (Java 17 + Quarkus + OpenShift)                      │
│                                                                    │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │  • Upload X-ray Image                                    │     │
│  │  • Display Detection Results                             │     │
│  │  • Show Traveler Background Data                         │     │
│  │  • Security Action Recommendation                        │     │
│  └─────────────────────────────────────────────────────────┘     │
└──────────────────────────┬───────────────────────────────────────┘
                           │ REST API Call
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│              PYTHON AI DETECTION SERVICE                          │
│                    (FastAPI + httpx)                               │
│                                                                    │
│  ┌────────────────────┐         ┌────────────────────────┐       │
│  │  Remote Model Call │         │   FBI Database         │       │
│  │  (KServe v1 API)   │────┐    │   Record Correlation   │       │
│  │                     │    │    │   (Warrants + Arrests) │       │
│  └─────────┬──────────┘    │    └───────────┬────────────┘       │
│            │               │                 │                    │
│            │    ┌──────────┴─────────┐       │                    │
│            │    │  OpenShift AI /    │       │                    │
│            │    │  KServe / GPU      │       │                    │
│            │    │  Model Server      │       │                    │
│            │    └────────────────────┘       │                    │
│            └────────────┬───────────────────┘                    │
│                         ▼                                         │
│            ┌─────────────────────────┐                            │
│            │  Security Logic Engine  │                            │
│            │  Risk Assessment &      │                            │
│            │  Action Recommendation  │                            │
│            └─────────────────────────┘                            │
└──────────────────────────────────────────────────────────────────┘
                           │
                           ▼
                ┌──────────────────────┐
                │   JSON Response:     │
                │ • Detections         │
                │ • Traveler Profile   │
                │ • Recommendation     │
                └──────────────────────┘
```

The system is composed of **three independently deployable components**:

| Component | Namespace | Description |
|---|---|---|
| **Quarkus Frontend** | `tsa-ai-screening` | Java web UI for TSA operators |
| **Python AI Service** | `tsa-ai-screening` | FastAPI backend that orchestrates model calls + data correlation |
| **DETR Model Server** | `demo-models` (or any model-serving namespace) | GPU-accelerated KServe InferenceService running the DETR weapon detection model |

## Technology Stack

### Backend AI Service (`/backend`)
- **Language**: Python 3.11+
- **Framework**: FastAPI (async REST API)
- **Inference**: Calls a remotely hosted DETR model via KServe v1 predict API
- **Libraries**: httpx (async HTTP), Pillow (image processing), Pandas (data correlation)

### Frontend Web Interface (`/frontend`)
- **Language**: Java 17
- **Framework**: Quarkus 3.8.3
- **Architecture**: RESTEasy Reactive + Qute templating
- **Build**: Multi-stage Docker build (builder + runtime)

### Model Serving
- **Model**: `NabilaLM/detr-weapons-detection` (DETR fine-tuned on X-ray weapon imagery)
- **Runtime**: Custom KServe ServingRuntime on Red Hat OpenShift AI
- **API**: KServe v1 predict (`POST /v1/models/{name}:predict`)

## Prerequisites

- **OpenShift**: 4.12+ with `oc` CLI authenticated
- **Red Hat OpenShift AI (RHOAI)**: Installed on the cluster for model serving
- **GPU Node**: At least one GPU worker node for model inference (or CPU with slower performance)
- **Namespace**: A project/namespace for the app (e.g., `tsa-ai-screening`)

## Deployment

### Step 1: Deploy the DETR Model on OpenShift AI

The model must be served via KServe before the app can function. You need a **ServingRuntime** and an **InferenceService** in a model-serving namespace (e.g., `demo-models`).

#### 1a. Create the ServingRuntime

```bash
oc apply -n demo-models -f - <<'EOF'
apiVersion: serving.kserve.io/v1alpha1
kind: ServingRuntime
metadata:
  name: detr-weapons-detection-runtime
spec:
  supportedModelFormats:
    - name: detr
      autoSelect: true
  containers:
    - name: kserve-container
      image: image-registry.openshift-image-registry.svc:5000/<your-namespace>/detr-weapons-detection:latest
      ports:
        - containerPort: 8080
          protocol: TCP
      env:
        - name: MODEL_NAME
          value: detr-weapons-detection
EOF
```

> **Note**: The container image must implement the KServe v1 predict API and accept base64-encoded images as input instances.

#### 1b. Create the InferenceService

```bash
oc apply -n demo-models -f - <<'EOF'
apiVersion: serving.kserve.io/v1beta1
kind: InferenceService
metadata:
  name: detr-weapons-detection
spec:
  predictor:
    model:
      runtime: detr-weapons-detection-runtime
      modelFormat:
        name: detr
EOF
```

#### 1c. Expose the Model Externally (Optional)

If the app namespace differs from the model namespace, create a route:

```bash
# Create an external service pointing to the predictor
oc expose deployment detr-weapons-detection-predictor \
  --name=detr-weapons-detection-external \
  --port=8080 -n demo-models

# Create a route
oc create route edge detr-weapons-detection \
  --service=detr-weapons-detection-external \
  --port=8080 -n demo-models
```

Verify the model is serving:

```bash
MODEL_URL=$(oc get route detr-weapons-detection -n demo-models -o jsonpath='{.spec.host}')
curl -sk "https://$MODEL_URL/v1/models/detr-weapons-detection"
# Expected: {"name":"detr-weapons-detection","ready":true}
```

### Step 2: Create the App Namespace

```bash
oc new-project tsa-ai-screening
```

### Step 3: Deploy the Python Backend

```bash
cd backend

# Create build config (S2I)
oc new-build python:3.11 --name=python-ai-service --binary=true -n tsa-ai-screening

# Build from local source
oc start-build python-ai-service --from-dir=. --follow -n tsa-ai-screening

# Create deployment
oc new-app python-ai-service --name=python-ai-service -n tsa-ai-screening

# Set the model endpoint URL
MODEL_ROUTE=$(oc get route detr-weapons-detection -n demo-models -o jsonpath='{.spec.host}')
oc set env deployment/python-ai-service \
  MODEL_SERVICE_URL="https://$MODEL_ROUTE" \
  MODEL_NAME=detr-weapons-detection \
  -n tsa-ai-screening

# Expose the service (internal only — the frontend connects to this)
oc expose deployment python-ai-service --port=8080 -n tsa-ai-screening
```

### Step 4: Deploy the Quarkus Frontend

```bash
cd frontend

# Create build config (Docker strategy using the included Dockerfile)
oc new-build --name=quarkus-frontend --binary=true \
  --strategy=docker -n tsa-ai-screening

# Build from local source
oc start-build quarkus-frontend --from-dir=. --follow -n tsa-ai-screening

# Create deployment
oc new-app quarkus-frontend --name=quarkus-frontend -n tsa-ai-screening

# Point the frontend at the backend service
oc set env deployment/quarkus-frontend \
  QUARKUS_REST_CLIENT_DETECTION_API_URL=http://python-ai-service:8080 \
  -n tsa-ai-screening

# Expose the service
oc expose deployment quarkus-frontend --port=8080 -n tsa-ai-screening

# Create a public route with TLS
oc create route edge scanner-ui \
  --service=quarkus-frontend --port=8080 -n tsa-ai-screening
```

### Step 5: Verify

```bash
# All pods should be Running
oc get pods -n tsa-ai-screening

# Get the app URL
oc get route scanner-ui -n tsa-ai-screening -o jsonpath='https://{.spec.host}'
```

Open the URL in your browser, upload an X-ray image, and click **START SECURITY ANALYSIS**.

## Configuration

### Backend Environment Variables

| Variable | Default | Description |
|---|---|---|
| `MODEL_SERVICE_URL` | `https://detr-weapons-detection-demo-models.apps.aromerot.redhat-openshift.com` | Base URL of the KServe model endpoint |
| `MODEL_NAME` | `detr-weapons-detection` | Model name registered in the serving runtime |

### Frontend Environment Variables

| Variable | Default | Description |
|---|---|---|
| `QUARKUS_REST_CLIENT_DETECTION_API_URL` | `http://python-ai-service:8080` | Internal URL of the Python backend service |

## Rebuilding After Code Changes

```bash
# Rebuild backend
cd backend
oc start-build python-ai-service --from-dir=. --follow -n tsa-ai-screening
oc rollout restart deployment/python-ai-service -n tsa-ai-screening

# Rebuild frontend
cd frontend
oc start-build quarkus-frontend --from-dir=. --follow -n tsa-ai-screening
oc rollout restart deployment/quarkus-frontend -n tsa-ai-screening
```

## Security Decision Logic

The system implements multi-factor risk assessment by correlating weapon detection results with criminal background data:

| Weapon Detected | Active Warrant | Prior Arrests | Action |
|---|---|---|---|
| Yes | Yes | Any | **CRITICAL ARREST** — Trap subject, notify law enforcement |
| Yes | No | Any | **LAW ENFORCEMENT DETAIN** — Notify police |
| No | Yes | Any | **DETAIN** — Active warrant alert |
| No | No | > 0 | **INTENSIVE SEARCH** — Manual bag inspection |
| No | No | 0 | **PASS** — Clear for travel |

## AI Model Details

**Model**: `NabilaLM/detr-weapons-detection`
- DETR (Detection Transformer) fine-tuned on X-ray weapon imagery
- Detects: guns, pistols, knives, and other prohibited items
- Returns bounding boxes with confidence scores via KServe v1 API

**Detection Output** (from the backend `/analyze` endpoint):
```json
{
  "traveler": {
    "name": "Jane Doe",
    "origin": "United States",
    "dob": "1990-05-20",
    "history": { "prior_arrests": 1, "warrants": "No", "charges": "Trespassing" }
  },
  "detections": [
    { "label": "WEAPON", "confidence": 0.8745, "box": [123.45, 67.89, 345.67, 234.56] }
  ],
  "recommendation": "⛔️ LAW ENFORCEMENT DETAIN:\nProhibited weapon detected.\n🚨 Notify law enforcement."
}
```

## Troubleshooting

### "Neural Link Error: Check container logs"

The frontend cannot reach the backend, or the backend failed processing. Check the backend logs:

```bash
oc logs deployment/python-ai-service -n tsa-ai-screening --tail=50
```

Common causes:
- **Backend pod not running**: `oc get pods -n tsa-ai-screening`
- **Model server unreachable**: `curl -sk https://<model-route>/v1/models/detr-weapons-detection`
- **Model response format changed**: Check for parsing errors in the logs

### Frontend shows "SYSTEM OFFLINE"

The frontend health check to the backend is failing:

```bash
oc exec deployment/quarkus-frontend -n tsa-ai-screening -- curl -s http://python-ai-service:8080/health
```

### Build fails with permission errors

The frontend Dockerfile runs as non-root. If the Maven build fails with permission errors, ensure the Dockerfile has:

```dockerfile
USER root
WORKDIR /build
COPY pom.xml .
COPY src src
RUN chown -R 185:0 /build && chmod -R g=u /build
USER 185
RUN mvn clean package -DskipTests
```

## Project Structure

```
ai-demo/
├── backend/
│   ├── app.py              # FastAPI application (model calls + correlation logic)
│   ├── records-db.csv      # Sample traveler database
│   └── requirements.txt    # Python dependencies (fastapi, httpx, pillow, pandas)
├── frontend/
│   ├── Dockerfile          # Multi-stage build for OpenShift
│   ├── pom.xml             # Maven build config (Quarkus 3.8.3)
│   └── src/
│       └── main/
│           ├── java/com/redhat/aidemo/detection/
│           │   ├── DetectionClient.java    # REST client interface to backend
│           │   ├── DetectionResponse.java  # Response data model
│           │   └── ScannerResource.java    # /scan endpoint
│           └── resources/
│               ├── application.properties  # Quarkus config (backend URL, body size limit)
│               └── META-INF/resources/
│                   └── index.html          # Scanner UI
└── README.md
```

## Architecture Decisions

### Why Remote Model Serving?
- **Lightweight backend**: No ML frameworks or model weights — just HTTP calls
- **GPU acceleration**: Model runs on GPU nodes via KServe; backend runs on CPU
- **Independent scaling**: Scale the UI, backend, and model server separately
- **Model swapping**: Change models by updating a URL — no code changes

### Why Quarkus for Frontend?
- **Fast startup**: <1 second, critical for scaling
- **Low memory**: ~70MB RAM per pod
- **OpenShift native**: Built-in Kubernetes deployment support

### Why DETR?
- **Transformer architecture**: Superior accuracy on complex X-ray imagery
- **Pre-trained**: Available on Hugging Face with weapons detection fine-tuning
- **No anchor boxes**: Simpler architecture, easier to fine-tune for new threat categories

## License

This demonstration application is provided for evaluation purposes only.

**Disclaimer**: This repository does NOT contain actual TSA data, real FBI/DHS credentials, classified information, or production-ready code.

## Resources

- [Quarkus Documentation](https://quarkus.io/guides/)
- [DETR Model Paper](https://arxiv.org/abs/2005.12872) — "End-to-End Object Detection with Transformers" (Carion et al., 2020)
- [Red Hat OpenShift AI](https://www.redhat.com/en/technologies/cloud-computing/openshift/openshift-ai)
- [KServe Documentation](https://kserve.github.io/website/)
