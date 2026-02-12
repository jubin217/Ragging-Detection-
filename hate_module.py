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
            "custom_keyword": False
        }

        self.recognizer = sr.Recognizer()

    def start(self):
        threading.Thread(target=self.run, daemon=True).start()

    def run(self):

        mic = sr.Microphone()
        with mic as source:
            self.recognizer.adjust_for_ambient_noise(source)

        while True:
            with mic as source:
                audio = self.recognizer.listen(source)

            try:
                text = self.recognizer.recognize_google(audio, language="ml-IN")

                # keyword check
                hit = self.km.match_keyword(text)

                if hit:
                    self.signals["custom_keyword"] = True
                    self.signals["hate_speech"] = True
                else:
                    result = self.detector.analyze_text(text)
                    self.signals["hate_speech"] = (
                        result["prediction"] == "ABUSIVE"
                    )
                    self.signals["custom_keyword"] = False

            except:
                pass

    def get_state(self):
        return self.signals
