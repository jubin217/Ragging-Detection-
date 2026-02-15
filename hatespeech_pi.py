# hatespeech_pi.py
import sys
import time
import threading
import speech_recognition as sr

from malayalam_hate_detector import ContinuousMalayalamDetector as BaseDetector
from keywords_manager import KeywordsManager

# =========================
# HELPER: FIND USB MIC
# =========================
def get_usb_mic_index():
    """
    Scans available microphones and returns the index of the first one
    that contains 'USB' in its name. Returns None if not found.
    """
    print("🔍 Scanning for USB Microphone...")
    mic_list = sr.Microphone.list_microphone_names()
    
    for i, name in enumerate(mic_list):
        print(f"  [{i}] {name}")
        if "USB" in name:
            print(f"✅ Found USB Mic: '{name}' at index {i}")
            return i
            
    print("⚠️ No USB Mic found. Using default device.")
    return None

# --------------------------------------------------
# EXTENDED DETECTOR (Package + Custom Keywords)
# --------------------------------------------------
class KeywordAwareMalayalamDetector(BaseDetector):
    def __init__(self, keywords_file="custom_keywords.txt"):
        print("⏳ Loading Hate Speech Detection Model...")
        super().__init__()  # 🔥 this loads MuRIL model
        self.km = KeywordsManager(keywords_file)
        print("✅ Model loaded")

    def analyze_text(self, text):
        #1️⃣ Rule-based override FIRST
        hit = self.km.match_keyword(text)
        if hit:
            return {
                "text": text,
                "prediction": "ABUSIVE",
                "confidence": 0.999,
                "reason": f"keyword:{hit}",
                "timestamp": time.time()
            }

        # 2️⃣ Otherwise fall back to ML model
        return super().analyze_text(text)


# --------------------------------------------------
# REAL-TIME SPEECH LOOP
# --------------------------------------------------
def start_detection_with_keyboard_stop(detector: KeywordAwareMalayalamDetector):
    recognizer = detector.recognizer
    stop_event = threading.Event()

    def callback(recognizer, audio):
        try:
            # Using Google Speech Recognition (requires internet)
            # For offline on Pi, you might need Vosk or pocketsphinx
            text = recognizer.recognize_google(audio, language="ml-IN")
            print(f"\n🔊 Transcribed: {text}")

            if "stop" in text.lower():
                stop_event.set()
                return

            result = detector.analyze_text(text)

            if result["prediction"] == "ABUSIVE":
                print(f"🚨 ABUSIVE ({result['confidence']:.2%}) | {result.get('reason','ML')}")
            else:
                print(f"✅ NORMAL ({result['confidence']:.2%})")

        except sr.UnknownValueError:
            pass # print("❓ Audio unclear")
        except sr.RequestError as e:
            print(f"⚠️ Network error: {e}")
        except Exception as e:
            print("⚠️ Error:", e)

    # Auto-detect USB Mic
    device_index = get_usb_mic_index()
    
    # Initialize Mic manually with specific index
    mic = sr.Microphone(device_index=device_index)
    
    print("🎤 Adjusting for ambient noise... (Please be quiet)")
    with mic as source:
        recognizer.adjust_for_ambient_noise(source, duration=2)
    print("✅ Ready!")

    # Start background listening
    stop_listening = recognizer.listen_in_background(
        mic, callback, phrase_time_limit=8
    )

    print("\n🎤 Malayalam Hate Speech Detection Started (Pi Version)")
    print("• Speak normally")
    print("• Say 'stop' or press q + ENTER to quit\n")

    try:
        while not stop_event.is_set():
            if sys.stdin in select_read():
                line = sys.stdin.readline()
                if line and line.strip().lower() == "q":
                    break
            time.sleep(0.1)
    finally:
        stop_listening(wait_for_stop=False)
        print("🛑 Stopped cleanly")


def select_read():
    if sys.platform.startswith("win"):
        import msvcrt
        return [sys.stdin] if msvcrt.kbhit() else []
    else:
        import select
        return select.select([sys.stdin], [], [], 0)[0]


# --------------------------------------------------
# MAIN
# --------------------------------------------------
if __name__ == "__main__":
    detector = KeywordAwareMalayalamDetector("custom_keywords.txt")
    start_detection_with_keyboard_stop(detector)
