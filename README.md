# ResQvoice AI (Python Decision Engine)

This is the primary Python backend for the ResQvoice system. It uses a **multi-threaded architecture** on Raspberry Pi edge devices to concurrently run YOLOv8 Pose tracking for physical fight detection and real-time audio analysis for hateful and abusive speech.

## Features
- **YOLOv8 Pose Skeleton**: Tracks humans and computes acceleration vectors to determine if a physical altercation is occurring.
- **Continuous Audio AI**: Sub-thread execution processes raw mic data concurrently against a PyTorch engine to detect abusive language.
- **Multi-Device Cloud Linking**: Secure JSON configuration dynamically syncs edge inferences directly to Firebase so remote administrators see live reports across many physical sites simultaneously.

---

## 🚀 Raspberry Pi Installation

### 1. Install System Dependencies
Before installing Python packages, you **must** install these system-level audio headers for PyAudio to compile correctly on Linux/Pi:
```bash
sudo apt-get update
sudo apt-get install portaudio19-dev python3-pyaudio -y
sudo apt-get install libatlas-base-dev -y
```

### 2. Create Python Environment
*Note: Because of potential package conflicts on Raspberry Pi OS Bookworm, creating a virtual environment is highly recommended.*
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Python Dependencies
```bash
pip install -r requirements.txt
```
*(We specifically use `numpy==1.26.4` and `opencv-python-headless` to bypass the notorious "Illegal instruction" errors that plague Raspberry Pis with newer ABI packages).*

---

## ⚙️ Running the Engine

1. Open `pi_credentials.json` and insert the specific user's Email and Password that you registered on your web dashboard.
2. Ensure you have the weights (`Yolo_nano_weights.pt` and `yolov8n-pose.pt`) inside the root directory.
3. Run the engine:
```bash
python decision_engine_pi.py
```

The script will hook onto your Picamera2 module, start real-time telemetry, and push any detected anomalies seamlessly to the isolated Web Dashboard feed!

> **Web Dashboard Note**: The interactive React dashboard code lives inside the `/web_dashboard` project folder and runs entirely independently of this hardware script.
