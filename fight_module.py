# fight_module.py
import threading
import cv2
import numpy as np
from ultralytics import YOLO


class FightDetector:

    def __init__(self):
        self.det_model = YOLO("yolo_small_weights.pt")
        self.pose_model = YOLO("yolov8s-pose.pt")

        self.signals = {
            "yolo_violence": False,
            "pose_aggressive": False,
            "sudden_motion": False
        }

        self.prev_gray = None
        self.prev_keypoints = None

        # Use 0 first — change to 1 only if needed
        self.cap = cv2.VideoCapture(1)

        if not self.cap.isOpened():
            raise RuntimeError("❌ Camera not accessible")

    def start(self):
        threading.Thread(target=self.run, daemon=True).start()

    def run(self):
        print("📷 Fight Detection Started")

        while True:
            try:
                ret, frame = self.cap.read()
                if not ret:
                    continue

                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

                # ----------------------------
                # YOLO Detection
                # ----------------------------
                yolo_violence = False
                det_results = self.det_model(frame, conf=0.6, verbose=False)

                if det_results and det_results[0].boxes:
                    for box in det_results[0].boxes:
                        if int(box.cls) == 1:
                            yolo_violence = True

                # ----------------------------
                # Pose Detection
                # ----------------------------
                pose_aggressive = False
                pose_results = self.pose_model(frame, verbose=False)

                if pose_results and pose_results[0].keypoints is not None:
                    curr = pose_results[0].keypoints.xy.cpu().numpy()

                    if (
                        self.prev_keypoints is not None
                        and len(curr) > 0
                        and len(self.prev_keypoints) > 0
                        and curr.shape == self.prev_keypoints.shape
                    ):
                        diffs = np.linalg.norm(
                            curr[0] - self.prev_keypoints[0], axis=1
                        )
                        if diffs.size > 0 and np.max(diffs) > 35:
                            pose_aggressive = True

                    self.prev_keypoints = curr
                else:
                    self.prev_keypoints = None

                # ----------------------------
                # Optical Flow
                # ----------------------------
                sudden_motion = False
                if self.prev_gray is not None:
                    flow = cv2.calcOpticalFlowFarneback(
                        self.prev_gray, gray, None,
                        0.5, 3, 15, 3, 5, 1.2, 0
                    )
                    mag, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
                    if mag.mean() > 1.5:
                        sudden_motion = True

                self.prev_gray = gray

                # ----------------------------
                # Update signals
                # ----------------------------
                self.signals["yolo_violence"] = yolo_violence
                self.signals["pose_aggressive"] = pose_aggressive
                self.signals["sudden_motion"] = sudden_motion

                # ----------------------------
                # Display Window
                # ----------------------------
                status = "VIOLENCE" if yolo_violence else "NORMAL"
                color = (0, 0, 255) if yolo_violence else (0, 255, 0)

                cv2.putText(frame, status, (20, 40),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, color, 3)

                cv2.imshow("Fight Detection", frame)

                # Press q to close camera
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

            except Exception as e:
                print("⚠️ Fight thread error:", e)
                self.signals = {
                    "yolo_violence": False,
                    "pose_aggressive": False,
                    "sudden_motion": False
                }

        self.cap.release()
        cv2.destroyAllWindows()

    def get_state(self):
        return self.signals
