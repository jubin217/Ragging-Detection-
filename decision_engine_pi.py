import sys
import time
import threading
import collections
import os

# =========================
# PICAMERA2 HACK (MUST BE BEFORE CV2)
# =========================
picam2_paths = [
    "/usr/lib/python3/dist-packages",
    "/usr/lib/python3.11/dist-packages",
    "/usr/lib/python3.9/dist-packages",
]
for p in picam2_paths:
    if os.path.exists(p) and p not in sys.path:
        sys.path.append(p)

try:
    from picamera2 import Picamera2
    print("[DecisionEngine] Global import: Picamera2 loaded successfully.")
except ImportError:
    Picamera2 = None
    print("[DecisionEngine] Global import: Picamera2 not found (yet).")
except Exception as e:
    Picamera2 = None
    print(f"[DecisionEngine] Global import: Picamera2 error: {e}")

# Now safe to import cv2 and ultralytics
import cv2
import numpy as np
import speech_recognition as sr
from ultralytics import YOLO

# Import from our existing Pi scripts
from hatespeech_pi import KeywordAwareMalayalamDetector, get_usb_mic_index
from firebase_logger import FirebaseLogger
from gsm_alert import GSMNotifier

# =========================
# GLOBALS & TUNABLES
# =========================
CONF_THRESHOLD = 0.45
POSE_SPEED_THRESHOLD = 25
FLOW_THRESHOLD = 1.0
RESOLUTION = (640, 480)
FRAMERATE = 30

# State Tracking (Timestamps)
fight_events = collections.deque()
hate_events = collections.deque()

# Threads sync
stop_event = threading.Event()

# =========================
# CAMERA SETUP (From fight_pi)
# =========================
class PiCamera2Wrapper:
    def __init__(self):
        self.is_running = False
        self.picam2 = None
        
        if Picamera2 is None:
            print("⚠️ Picamera2 library not declared globally.")
            return

        try:
            self.picam2 = Picamera2()
            self.picam2.preview_configuration.main.size = RESOLUTION
            self.picam2.preview_configuration.main.format = "RGB888"
            self.picam2.configure("preview")
            self.picam2.start()
            
            time.sleep(2)
            self.is_running = True
            print("✅ Picamera2 initialized successfully!")
        except Exception as e:
            print(f"⚠️ Picamera2 init failed: {e}")
            if self.picam2:
                self.picam2.stop()
            self.is_running = False

    def read(self):
        if not self.is_running:
            return False, None
        try:
            frame = self.picam2.capture_array()
            if frame is not None:
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            return True, frame
        except Exception as e:
            print(f"⚠️ Picamera2 capture failed: {e}")
            return False, None
    
    def isOpened(self):
        return self.is_running

    def release(self):
        if self.is_running:
            self.picam2.stop()
            self.is_running = False

def open_camera():
    # 0. Try Picamera2
    print("[DecisionEngine] Attempting Picamera2...")
    try:
        picam = PiCamera2Wrapper()
        if picam.isOpened():
            return picam
    except Exception as e:
        print(f"⚠️ Picamera2 failed: {e}")

    # 1. Try GStreamer Pipeline
    print("[DecisionEngine] Attempting GStreamer pipeline (libcamerasrc)...")
    gst_pipeline = (
        f"libcamerasrc ! video/x-raw, width={RESOLUTION[0]}, height={RESOLUTION[1]}, framerate={FRAMERATE}/1 ! "
        "videoconvert ! videoscale ! video/x-raw, format=BGR ! appsink drop=1"
    )
    cap = cv2.VideoCapture(gst_pipeline, cv2.CAP_GSTREAMER)
    
    if cap.isOpened():
        ret, _ = cap.read()
        if ret:
            print("✅ GStreamer pipeline opened and reading frames!")
            return cap
        else:
            print("⚠️ GStreamer opened but failed to read frame.")
            cap.release()
    else:
        print("⚠️ GStreamer pipeline failed to open.")

    # 2. Try standard indices
    indices = [0, -1, 1]
    for idx in indices:
        print(f"[DecisionEngine] Attempting to open camera index {idx}...")
        cap = cv2.VideoCapture(idx, cv2.CAP_V4L2)
        if not cap.isOpened():
            cap = cv2.VideoCapture(idx)
        
        if cap.isOpened():
            # FORCE MJPG
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, RESOLUTION[0])
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, RESOLUTION[1])
            
            ret, _ = cap.read()
            if ret:
                print(f"✅ Camera index {idx} opened with MJPG!")
                return cap
            
            # If MJPG failed, try YUYV
            print(f"⚠️ Index {idx} MJPG failed, trying YUYV...")
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('Y', 'U', 'Y', 'V'))
            ret, _ = cap.read()
            if ret:
                print(f"✅ Camera index {idx} opened with YUYV!")
                return cap

            print(f"⚠️ Camera index {idx} opened but failed to read frame. releasing...")
            cap.release()
    return None

# =========================
# HELPER FUNCTIONS
# =========================
def compute_optical_flow(prev, curr):
    flow = cv2.calcOpticalFlowFarneback(
        prev, curr, None,
        0.5, 3, 15, 3, 5, 1.2, 0
    )
    mag, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
    return mag.mean()

def aggressive_pose(prev_kp, curr_kp):
    if prev_kp is None or curr_kp is None:
        return False
    if len(prev_kp) == 0 or len(curr_kp) == 0:
        return False

    prev = prev_kp[0]
    curr = curr_kp[0]

    if prev.shape != curr.shape:
        return False

    diffs = np.linalg.norm(curr - prev, axis=1)
    return diffs.size > 0 and np.max(diffs) > POSE_SPEED_THRESHOLD


# =========================
# BACKGROUND SPEECH PROCESS
# =========================
def start_speech_listener():
    detector = KeywordAwareMalayalamDetector("custom_keywords.txt")
    recognizer = sr.Recognizer()

    def callback(recognizer, audio):
        if stop_event.is_set():
            return
            
        try:
            text = recognizer.recognize_google(audio, language="ml-IN")
            print(f"\n🔊 Transcribed: {text}")

            result = detector.analyze_text(text)
            if result["prediction"] == "ABUSIVE":
                hate_events.append(time.time())
                print(f"🚨 HATESPEECH DETECTED ({result['confidence']:.2%}) | {result.get('reason','ML')}")

        except sr.UnknownValueError:
            pass # Unclear audio
        except sr.RequestError as e:
            print(f"⚠️ Network error: {e}")
        except Exception as e:
            print("⚠️ Hate Speech Engine Error:", e)

    # Auto-detect USB Mic
    device_index = get_usb_mic_index()
    mic = sr.Microphone(device_index=device_index)
    
    print("🎤 Adjusting for ambient noise... (Please be quiet)")
    with mic as source:
        recognizer.adjust_for_ambient_noise(source, duration=2)
    print("✅ Microphone Ready!")

    # Start background listening
    stop_listening = recognizer.listen_in_background(
        mic, callback, phrase_time_limit=8
    )
    return stop_listening

# =========================
# DECISION LOGIC
# =========================
def evaluate_ragging(now):
    # Retrieve 30-second moving windows specifically for Rule 1
    fight_30s = sum(1 for t in fight_events if now - t <= 30)
    hate_30s = sum(1 for t in hate_events if now - t <= 30)

    # Total lifetime events (No time limit)
    total_fights = len(fight_events)
    total_hate = len(hate_events)

    decision = "NORMAL"

    # Rule 1: if fight >= 4 and hate speech >= 2 within 30 sec, ragging detected
    if fight_30s >= 4 and hate_30s >= 2:
        decision = "RAGGING DETECTED"
    # Rule 2: if fight >= 5, ragging possibility (No time limit)
    elif total_fights >= 5:
        decision = "RAGGING POSSIBILITY"
    # Rule 4: If hate speech >= 4, potential ragging (No time limit)
    elif total_hate >= 4:
        decision = "POTENTIAL RAGGING"
    # Rule 3: if fight from 1 to 3, suspicious activity (No time limit)
    elif 1 <= total_fights <= 3:
        decision = "SUSPICIOUS ACTIVITY"

    return decision, fight_30s, total_fights, total_hate

# =========================
# MAIN
# =========================
def main():
    print("⏳ Loading YOLO models... (This may take a while on Pi)")
    det_model = YOLO("Yolo_nano_weights.pt")   # violence detector (nano)
    pose_model = YOLO("yolov8n-pose.pt")       # pose estimator (nano)
    print("✅ Models loaded")

    camera = open_camera()
    if camera is None:
        print("❌ CRITICAL: Could not open any camera.")
        sys.exit(1)

    print("✅ Initializing Hate Speech Thread...")
    stop_listening = start_speech_listener()

    print("✅ Initializing Firebase Logger...")
    firebase_logger = FirebaseLogger()

    print("✅ Initializing GSM Module...")
    gsm_notifier = GSMNotifier()

    print("✅ Real-time Unified Decision Engine Started")

    prev_gray = None
    prev_keypoints = None
    last_decision = "NORMAL"

    try:
        while not stop_event.is_set():
            ret, frame = camera.read()
            if not ret:
                print("⚠️ Camera read failed (empty frame)")
                time.sleep(0.1)
                continue
            
            # Optical flow setup
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # -------------------------
            # YOLO VIOLENCE (TRIGGER)
            # -------------------------
            yolo_violence = False
            det_results = det_model(frame, conf=CONF_THRESHOLD, verbose=False)

            if det_results and det_results[0].boxes:
                for box in det_results[0].boxes:
                    if int(box.cls) == 1 and float(box.conf) >= CONF_THRESHOLD:
                        yolo_violence = True
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)

            # -------------------------
            # POSE & FLOW (Optional support signals)
            # -------------------------
            pose_results = pose_model(frame, verbose=False)
            if pose_results and pose_results[0].keypoints is not None:
                curr_keypoints = pose_results[0].keypoints.xy.cpu().numpy()
                pose_aggressive = aggressive_pose(prev_keypoints, curr_keypoints)
                prev_keypoints = curr_keypoints
                
                # Draw Skeleton (Red if fight detected, otherwise Green)
                kp_color = (0, 0, 255) if yolo_violence else (0, 255, 0)
                SKELETON_PAIRS = [
                    (0, 1), (0, 2), (1, 3), (2, 4), (5, 6), (5, 7), (7, 9), 
                    (6, 8), (8, 10), (5, 11), (6, 12), (11, 12), (11, 13), 
                    (13, 15), (12, 14), (14, 16)
                ]
                for person_kps in curr_keypoints:
                    for kp in person_kps:
                        x, y = int(kp[0]), int(kp[1])
                        if x != 0 and y != 0:
                            cv2.circle(frame, (x, y), 4, kp_color, -1)
                            
                    for p1, p2 in SKELETON_PAIRS:
                        if p1 < len(person_kps) and p2 < len(person_kps):
                            x1, y1 = int(person_kps[p1][0]), int(person_kps[p1][1])
                            x2, y2 = int(person_kps[p2][0]), int(person_kps[p2][1])
                            if x1 != 0 and y1 != 0 and x2 != 0 and y2 != 0:
                                cv2.line(frame, (x1, y1), (x2, y2), kp_color, 2)
            else:
                prev_keypoints = None
                pose_aggressive = False

            if prev_gray is not None:
                flow_score = compute_optical_flow(prev_gray, gray)
                sudden_motion = flow_score > FLOW_THRESHOLD
            else:
                sudden_motion = False
            prev_gray = gray

            # Log Fight Detections based on YOLO model
            now = time.time()
            if yolo_violence:
                fight_events.append(now)

            # Evaluate the system state
            decision, f_30s, total_f, total_h = evaluate_ragging(now)

            # If the state changed, print to terminal
            if decision != last_decision and decision != "NORMAL":
                print(f"[{time.strftime('%H:%M:%S')}] 🚨 {decision.upper()} 🚨")
                is_emergency = (decision == "RAGGING DETECTED")
                
                # Save frame temporarily for evidence upload
                evidence_path = f"evidence_{int(time.time())}.jpg"
                cv2.imwrite(evidence_path, frame)
                
                # Push visual evidence to Firebase
                threading.Thread(target=firebase_logger.log_with_evidence, args=(decision, is_emergency, evidence_path), daemon=True).start()
                
                # Dispatch SMS to authorized authorities via GSM
                gsm_notifier.trigger_sms(decision)
            last_decision = decision

            # -------------------------
            # DISPLAY STATUS
            # -------------------------
            color = (0, 255, 0)
            if decision == "RAGGING DETECTED":
                color = (0, 0, 255)
            elif decision == "POTENTIAL RAGGING":
                color = (0, 140, 255)
            elif decision == "RAGGING POSSIBILITY":
                color = (0, 165, 255)
            elif decision == "SUSPICIOUS ACTIVITY":
                color = (0, 255, 255)

            cv2.putText(frame, f"STATUS: {decision}", (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, color, 3)

            # Debug counts
            cv2.putText(frame, f"Fights (30s): {f_30s}", (20, 80),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 2)
            cv2.putText(frame, f"Fights (Total): {total_f}", (20, 110),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 2)
            cv2.putText(frame, f"Hate (Total): {total_h}", (20, 140),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 2)

            try:
                cv2.imshow("Unified Decision Engine", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    stop_event.set()
                    break
            except Exception:
                pass

    except Exception as e:
        print(f"❌ Core Loop Error: {e}")

    finally:
        print("🛑 Cleaning up resources...")
        stop_event.set()
        if 'stop_listening' in locals() and stop_listening:
            stop_listening(wait_for_stop=False)
        if camera:
            camera.release()
        try:
            cv2.destroyAllWindows()
        except:
            pass

if __name__ == "__main__":
    main()
