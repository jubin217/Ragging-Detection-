# hate_module.py
import threading
import speech_recognition as sr
from malayalam_hate_detector import ContinuousMalayalamDetector
from keywords_manager import KeywordsManager


class HateDetector:

    def __init__(self):
        self.detector = ContinuousMalayalamDetector()
        self.km = KeywordsManager("custom_keywords.txt")

        self.signals = {
            "hate_speech": False,
            "custom_keyword": False,
            "last_text": "",
            "last_result": "NORMAL"
        }

        self.recognizer = sr.Recognizer()

    def start(self):
        threading.Thread(target=self.run, daemon=True).start()

    def run(self):

        mic = sr.Microphone()
        with mic as source:
            self.recognizer.adjust_for_ambient_noise(source)

        print("🎤 Hate Speech Detection Started")

        while True:
            try:
                with mic as source:
                    audio = self.recognizer.listen(source)

                text = self.recognizer.recognize_google(audio, language="ml-IN")

                self.signals["last_text"] = text

                # Check custom keywords
                hit = self.km.match_keyword(text)

                if hit:
                    self.signals["custom_keyword"] = True
                    self.signals["hate_speech"] = True
                    self.signals["last_result"] = "ABUSIVE (KEYWORD)"

                else:
                    result = self.detector.analyze_text(text)

                    if result["prediction"] == "ABUSIVE":
                        self.signals["hate_speech"] = True
                        self.signals["custom_keyword"] = False
                        self.signals["last_result"] = "ABUSIVE (ML)"
                    else:
                        self.signals["hate_speech"] = False
                        self.signals["custom_keyword"] = False
                        self.signals["last_result"] = "NORMAL"

                # 🔥 PRINT VOICE DETECTION
                print(f"\n🎤 Voice Detected: {text}")
                print(f"🗣 Hate Speech Result: {self.signals['last_result']}")

            except Exception:
                pass

    def get_state(self):
        return self.signals