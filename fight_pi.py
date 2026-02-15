import cv2
import time
import numpy as np
from ultralytics import YOLO
from picamera.array import PiRGBArray
from picamera import PiCamera

# =========================
# LOAD MODELS
# =========================
print("⏳ Loading YOLO models... (This may take a while on Pi)")
det_model = YOLO("yolo_small_weights.pt")   # violence detector
pose_model = YOLO("yolov8s-pose.pt")        # pose estimator
print("✅ Models loaded")

# =========================
# PARAMETERS
# =========================
CONF_THRESHOLD = 0.6
POSE_SPEED_THRESHOLD = 35
FLOW_THRESHOLD = 1.5
RESOLUTION = (640, 480)
FRAMERATE = 30

# =========================
# STATE VARIABLES
# =========================
violence_active = False          # current state
violence_announced = False       # terminal print control

prev_gray = None
prev_keypoints = None

# =========================
# SETUP CAMERA
# =========================
print("📸 Initializing PiCamera...")
camera = PiCamera()
camera.resolution = RESOLUTION
camera.framerate = FRAMERATE
rawCapture = PiRGBArray(camera, size=RESOLUTION)

# Allow camera to warmup
time.sleep(2)
print("✅ Real-time Violence Detection Started (PiCamera)")

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
# MAIN LOOP
# =========================
try:
    for frame_obj in camera.capture_continuous(rawCapture, format="bgr", use_video_port=True):
        frame = frame_obj.array
        
        # Convert to grayscale for optical flow
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
        # POSE (SUPPORT SIGNAL)
        # -------------------------
        pose_aggressive = False
        pose_results = pose_model(frame, verbose=False)

        if pose_results and pose_results[0].keypoints is not None:
            curr_keypoints = pose_results[0].keypoints.xy.cpu().numpy()
            pose_aggressive = aggressive_pose(prev_keypoints, curr_keypoints)
            prev_keypoints = curr_keypoints
        else:
            prev_keypoints = None

        # -------------------------
        # OPTICAL FLOW (SUPPORT SIGNAL)
        # -------------------------
        sudden_motion = False
        if prev_gray is not None:
            flow_score = compute_optical_flow(prev_gray, gray)
            sudden_motion = flow_score > FLOW_THRESHOLD

        prev_gray = gray

        # =========================
        # FINAL DECISION (IMMEDIATE)
        # =========================
        if yolo_violence:
            violence_active = True

            if not violence_announced:
                print(f"[{time.strftime('%H:%M:%S')}] 🚨 VIOLENCE DETECTED 🚨")
                violence_announced = True
        else:
            violence_active = False
            violence_announced = False

        # -------------------------
        # DISPLAY STATUS
        # -------------------------
        status = "VIOLENCE" if violence_active else "NORMAL"
        color = (0, 0, 255) if violence_active else (0, 255, 0)

        cv2.putText(frame, f"STATUS: {status}", (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, color, 3)

        # Debug signals
        cv2.putText(frame, f"YOLO: {yolo_violence}", (20, 80),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 2)
        cv2.putText(frame, f"POSE: {pose_aggressive}", (20, 110),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 2)
        cv2.putText(frame, f"FLOW: {sudden_motion}", (20, 140),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 2)

        cv2.imshow("Violence Detection (PiCamera)", frame)
        
        # Clear the stream in preparation for the next frame
        rawCapture.truncate(0)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

except Exception as e:
    print(f"❌ Error: {e}")

finally:
    # =========================
    # CLEANUP
    # =========================
    print("Cleaning up resources...")
    camera.close()
    cv2.destroyAllWindows()
