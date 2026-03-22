# ResQvoice System Documentation

This document explains the entire technical architecture, data flow, and the specific artificially intelligent decision rules driving the ResQvoice system.

---

## 1. High-Level Architecture

ResQvoice is an edge-to-cloud surveillance platform designed to detect abuse and bullying (ragging) on school or university campuses. The system is broken into three main components:

1. **Edge Inference Node (Raspberry Pi)**: Runs `decision_engine_pi.py`. This acts as the "eyes and ears" using locally deployed PyTorch and YOLOv8 models. No video or audio is streamed over the internet; all AI processing happens strictly on the local device to ensure privacy and low latency.
2. **Cloud Mediator (Firebase)**: When a severe incident is detected, the Raspberry Pi securely pushes lightweight JSON telemetry (the type of incident and timestamp) up to Firebase Firestore.
3. **Web Dashboard (React PWA)**: Administrators view real-time synchronized alerts, geographical heatmaps, and graphical statistics on a highly stylish, responsive web platform.

---

## 2. Artificial Intelligence Modules

The decision engine runs **two parallel AI modules leveraging Multi-Threading**:

### A. Vision AI (Physical Violence Detection)
- Utilizes an ultralytics **YOLOv8 Nano Pose Model**.
- **Mechanism**: The model isolates human subjects in the camera feed and generates a 17-point skeletal wireframe for each person. 
- The system calculates the velocity and acceleration between frames for limbs (like wrists and ankles). If rapid, chaotic movement exceeding a specific mathematical threshold (`POSE_SPEED_THRESHOLD`) is detected, it flags a "Fight Frame".

### B. Acoustic AI (Hate Speech & Abuse Detection)
- Utilizes the **Malayalam Hate Detector** running continuously in a background thread.
- **Mechanism**: It listens to short bursts of audio buffer from a USB microphone, transcribes the speech on the fly, and cross-references it against a custom list of prohibited, abusive vocabulary (`custom_keywords.txt`) as well as the ML model's baseline toxic vocabulary. 

---

## 3. The Decision Engine (Rules)

The script `decision_engine_pi.py` acts as the brain. Rather than triggering an alarm the millisecond someone moves fast or says a bad word, it uses a **Temporal Windowing Queue**. It keeps a rolling memory of the last 20 seconds. 

The evaluation function looks at these queues every frame and applies the following strict rules:

### RULE 1: Severe Multimedia Disturbance
**Condition:** If the Vision AI detects physical fighting **4 or more times** AND Acoustic AI detects hate speech **2 or more times** within a **30-second** window.
- **Output:** `🚨 RAGGING DETECTED`

### RULE 2: Repeated Physical Violence
**Condition:** If the Vision AI detects physical fighting **5 or more times** in total (No time limit, evaluated over the lifetime of the session).
- **Output:** `⚠️ RAGGING POSSIBILITY`

### RULE 3: Suspicious Minor Physical Activity
**Condition:** If the Vision AI detects fighting between **1 to 3 times** in total (No time limit).
- **Output:** `🟡 SUSPICIOUS ACTIVITY`

### RULE 4: Heavy Verbal Abuse
**Condition:** If the Acoustic AI detects abusive hate speech **4 or more times** in total (No time limit).
- **Output:** `🟠 POTENTIAL RAGGING`

---

## 4. Multi-Device Scalability

To allow this system to be deployed across hundreds of classrooms:
- Each Raspberry Pi has its own `pi_credentials.json` file.
- The Python backend reads this file, signs into the cloud automatically, and secures its Firebase connection.
- All telemetry is walled off into isolated `users/{Device_ID}/alerts` databases. 
- When an Administrator logs into the Web Dashboard, the dashboard strictly queries incidents matching their specific device identity, rendering graphs solely for their governed territory.
