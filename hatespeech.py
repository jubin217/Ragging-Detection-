# test.py
# Robust cross-platform 'press q to quit' with speech_recognition listen_in_background
import sys
import time
import threading

import speech_recognition as sr

# Use keywords_manager to detect custom abusive phrases
from keywords_manager import KeywordsManager

# --- Detector class (uses keywords manager + fallback stub model) ---
class ContinuousMalayalamDetector:
    def __init__(self, keywords_file="custom_keywords.txt"):
        self.recognizer = sr.Recognizer()
        self.conversation_history = []
        # load keywords manager
        self.km = KeywordsManager(keywords_file)

    def analyze_text(self, text):
        """
        1) If any custom keyword/phrase matches -> ABUSIVE (high confidence)
        2) Else fallback to existing simple stub logic (or later you can call your real model)
        """
        if not text:
            return {
                "text": text,
                "prediction": "NORMAL",
                "confidence": 0.0,
                "timestamp": time.time()
            }

        # 1) keyword overlay check
        hit = self.km.match_keyword(text)
        if hit:
            res = {
                "text": text,
                "prediction": "ABUSIVE",
                "confidence": 0.999,
                "timestamp": time.time(),
                "reason": f"keyword_hit:{hit}"
            }
            self.conversation_history.append(res)
            return res

        # 2) fallback stub (original behaviour preserved: check for "poda"/"പോടാ")
        abusive = False
        t = text.lower()
        if "poda" in t or "പോടാ" in t:
            abusive = True

        res = {
            "text": text,
            "prediction": "ABUSIVE" if abusive else "NORMAL",
            "confidence": 0.9 if abusive else 0.95,
            "timestamp": time.time()
        }
        self.conversation_history.append(res)
        return res

    def show_history(self, n=5):
        print("\n=== Last {} items ===".format(n))
        for item in self.conversation_history[-n:]:
            tag = "🚨" if item["prediction"] == "ABUSIVE" else "✅"
            t = time.strftime("%H:%M:%S", time.localtime(item["timestamp"]))
            reason = item.get("reason", "")
            print(f"{t} {tag} {item['text']} ({item['confidence']:.2%}) {reason}")
        print("====================\n")


# --- End detector ---

def start_detection_with_keyboard_stop(detector: ContinuousMalayalamDetector):
    r = detector.recognizer

    # callback runs in background thread for each captured audio chunk
    def callback(recognizer, audio):
        try:
            # You can change language to "ml-IN" for Malayalam if using Google
            text = recognizer.recognize_google(audio, language="ml-IN")
            print("\n🔊 Transcribed:", text)
            # example check for voice commands
            if 'stop' in text.lower():
                print("🛑 Voice command 'stop' detected — will stop after this callback.")
                stop_event.set()
                return

            result = detector.analyze_text(text)
            if result['prediction'] == 'ABUSIVE':
                print(f"🚨 ABUSIVE detected! Confidence: {result['confidence']:.2%}  Reason: {result.get('reason','')}")
            else:
                print(f"✅ Normal (Confidence: {result['confidence']:.2%})")

        except sr.UnknownValueError:
            print("❓ Could not understand audio.")
        except sr.RequestError as e:
            print("⚠️ Speech API error:", e)
        except Exception as e:
            print("⚠️ Callback error:", e)

    # Start listening in background
    mic = sr.Microphone()
    with mic as source:
        r.adjust_for_ambient_noise(source, duration=1.0)
    stop_listening = r.listen_in_background(mic, callback, phrase_time_limit=8)
    print("🎤 Listening in background. Press 'q' then ENTER (Windows) or just press 'q' (Linux/macOS) to quit.")
    print("Or say 'stop' to stop by voice. Type 'history' then ENTER to show last detections.\n")

    try:
        # Main loop: watch for q pressed (cross-platform)
        while not stop_event.is_set():
            if is_input_available():
                # read input (this blocks only when input available)
                line = sys.stdin.readline().strip().lower()
                if line == "q" or line == "quit":
                    print("🛑 'q' detected on stdin — stopping listener.")
                    stop_event.set()
                    break
                elif line == "history":
                    detector.show_history()
                else:
                    print("💡 Commands: 'q' to quit, 'history' to show recent detections")
            else:
                # Sleep a short amount and loop to remain responsive
                time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n🛑 KeyboardInterrupt received — stopping.")
        stop_event.set()
    finally:
        # stop the background listener (non-blocking stop)
        stop_listening(wait_for_stop=False)
        # small delay to let background callback finish if it was running
        time.sleep(0.4)
        print("✅ Listener stopped. Exiting now.")
        detector.show_summary_if_any = getattr(detector, "show_summary", None)
        if callable(detector.show_summary_if_any):
            detector.show_summary_if_any()

# Cross-platform stdin availability check
def is_input_available():
    """
    Returns True if there's input available on sys.stdin.
    On Windows uses msvcrt.kbhit(), on Unix uses select.select().
    """
    if sys.platform.startswith("win"):
        try:
            import msvcrt
            return msvcrt.kbhit()
        except Exception:
            return False
    else:
        import select
        return select.select([sys.stdin], [], [], 0)[0] != []

# global stop event
stop_event = threading.Event()

if __name__ == "__main__":
    detector = ContinuousMalayalamDetector()

    # If you have your real ContinuousMalayalamDetector class that exposes
    # recognizer and analyze_text(), import it and use that instead.
    # Example:
    # from malayalam_hate_detector import ContinuousMalayalamDetector
    # detector = ContinuousMalayalamDetector()

    start_detection_with_keyboard_stop(detector)
