# decision_engine.py
import time


class DecisionEngine:
    def __init__(self):
        self.emergency_timer = None
        self.warning_timer = None

    def evaluate(self, signals):

        yolo_violence = signals["yolo_violence"]
        pose_aggressive = signals["pose_aggressive"]
        sudden_motion = signals["sudden_motion"]
        hate_speech = signals["hate_speech"]
        custom_keyword = signals["custom_keyword"]

        # --------------------------
        # EMERGENCY CONDITIONS
        # --------------------------

        emergency = False

        if yolo_violence and (hate_speech or custom_keyword):
            emergency = True

        if yolo_violence and pose_aggressive:
            emergency = True

        if custom_keyword and pose_aggressive:
            emergency = True

        # --------------------------
        # WARNING CONDITIONS
        # --------------------------

        warning = False

        if hate_speech:
            warning = True

        if pose_aggressive and sudden_motion:
            warning = True

        if yolo_violence:
            warning = True

        # --------------------------
        # PERSISTENCE CHECK (2 sec)
        # --------------------------

        now = time.time()

        if emergency:
            if self.emergency_timer is None:
                self.emergency_timer = now
            if now - self.emergency_timer > 2:
                return "EMERGENCY"
        else:
            self.emergency_timer = None

        if warning:
            if self.warning_timer is None:
                self.warning_timer = now
            if now - self.warning_timer > 1:
                return "WARNING"
        else:
            self.warning_timer = None

        return "NORMAL"
