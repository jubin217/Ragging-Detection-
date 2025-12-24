import cv2
import time
from ultralytics import YOLO

# =========================
# LOAD MODEL
# =========================
model = YOLO("yolo_small_weights.pt")  # update path if needed

# =========================
# PARAMETERS (TUNE CAREFULLY)
# =========================
CONF_THRESHOLD = 0.6        # ignore weak detections
REQUIRED_FRAMES = 10        # frames needed to confirm violence
FRAME_WINDOW = 2            # seconds window

# =========================
# STATE VARIABLES
# =========================
violence_frames = 0
violence_announced = False
start_time = time.time()

# =========================
# OPEN WEBCAM
# =========================
cap = cv2.VideoCapture(1)   # change to 0 if needed

if not cap.isOpened():
    print("❌ Webcam not accessible")
    exit()

print("✅ Real-time Violence Detection Started")

# =========================
# MAIN LOOP
# =========================
while True:
    ret, frame = cap.read()
    if not ret:
        break

    # YOLO inference
    results = model(frame, conf=CONF_THRESHOLD, verbose=False)

    violence_detected = False

    # -------------------------
    # DETECTION LOOP
    # -------------------------
    if results and results[0].boxes:
        for box in results[0].boxes:
            class_id = int(box.cls)
            confidence = float(box.conf)

            # class 1 = Violence
            if class_id == 1 and confidence >= CONF_THRESHOLD:
                violence_detected = True

                x1, y1, x2, y2 = map(int, box.xyxy[0])
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                cv2.putText(
                    frame,
                    f"VIOLENCE {confidence:.2f}",
                    (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 0, 255),
                    2
                )

    # =========================
    # TEMPORAL LOGIC
    # =========================
    current_time = time.time()

    if violence_detected:
        violence_frames += 1

    if current_time - start_time >= FRAME_WINDOW:
        violence_frames = 0
        start_time = current_time

    # =========================
    # FINAL DECISION
    # =========================
    if violence_frames >= REQUIRED_FRAMES:
        status = "VIOLENCE"
        color = (0, 0, 255)

        if not violence_announced:
            print(f"[{time.strftime('%H:%M:%S')}] 🚨 VIOLENCE DETECTED 🚨")
            violence_announced = True

    else:
        status = "NON-VIOLENCE"
        color = (0, 255, 0)
        violence_announced = False

    # -------------------------
    # DISPLAY STATUS
    # -------------------------
    cv2.putText(
        frame,
        f"STATUS: {status}",
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        color,
        3
    )

    cv2.imshow("Violence Detection (YOLOv8)", frame)

    # Exit
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# =========================
# CLEANUP
# =========================
cap.release()
cv2.destroyAllWindows()
