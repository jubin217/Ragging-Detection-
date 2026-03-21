import speech_recognition as sr
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
import time

class ContinuousMalayalamDetector:
    def __init__(self):
        # The model loading is hidden here
        self.tokenizer = AutoTokenizer.from_pretrained("Hate-speech-CNERG/malayalam-codemixed-abusive-MuRIL")
        self.model = AutoModelForSequenceClassification.from_pretrained("Hate-speech-CNERG/malayalam-codemixed-abusive-MuRIL")
        self.recognizer = sr.Recognizer()
        self.conversation_history = []
        
    def analyze_text(self, text):
        """Analyze text and return results"""
        inputs = self.tokenizer(text, return_tensors="pt", truncation=True, padding=True, max_length=128)
        with torch.no_grad():
            outputs = self.model(**inputs)
        
        probabilities = torch.nn.functional.softmax(outputs.logits, dim=-1)
        predicted_class = torch.argmax(probabilities, dim=1).item()
        confidence = probabilities[0][predicted_class].item()
        
        return {
            'text': text,
            'prediction': "ABUSIVE" if predicted_class == 1 else "NORMAL",
            'confidence': confidence,
            'normal_prob': probabilities[0][0].item(),
            'abusive_prob': probabilities[0][1].item(),
            'timestamp': time.time()
        }
    
    def start_continuous_detection(self):
        """Start continuous speech detection"""
        print("🎤 Malayalam Abuse Detection - Continuous Mode")
        print("=============================================")
        print("Commands: 'stop' - Exit, 'history' - Show history")
        print("Speak in Malayalam...\n")
        
        detection_count = 0
        abusive_count = 0
        
        while True:
            try:
                with sr.Microphone() as source:
                    self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                    print("🎯 Ready... Speak now!")
                    
                    audio = self.recognizer.listen(source, timeout=8, phrase_time_limit=12)
                
                print("🔄 Processing...")
                malayalam_text = self.recognizer.recognize_google(audio, language="ml-IN")
                
                # Check for commands
                if 'stop' in malayalam_text.lower():
                    break
                elif 'history' in malayalam_text.lower():
                    self.show_history()
                    continue
                
                # Analyze the text
                result = self.analyze_text(malayalam_text)
                self.conversation_history.append(result)
                detection_count += 1
                
                # Display results
                self.display_result(result, detection_count)
                
                if result['prediction'] == 'ABUSIVE':
                    abusive_count += 1
                
                print(f"📈 Stats: Total: {detection_count} | Abusive: {abusive_count}")
                print("-" * 60)
                
            except sr.WaitTimeoutError:
                print("⏰ Silence detected... still listening")
            except sr.UnknownValueError:
                print("❓ Audio unclear, please try again")
            except KeyboardInterrupt:
                print("\n🛑 Session ended by user")
                break
            except Exception as e:
                print(f"⚠️ Error: {e}")
        
        self.show_summary()
    
    def display_result(self, result, count):
        """Display analysis result with formatting"""
        print(f"\n#{count} | {time.strftime('%H:%M:%S')}")
        print(f"📝 Text: {result['text']}")
        
        if result['prediction'] == 'ABUSIVE':
            print(f"🚨 ABUSIVE CONTENT DETECTED!")
            print(f"📊 Confidence: {result['confidence']:.2%}")
        else:
            print(f"✅ Normal content")
            print(f"📊 Confidence: {result['confidence']:.2%}")
        
        print(f"📈 Probabilities - Normal: {result['normal_prob']:.2%} | Abusive: {result['abusive_prob']:.2%}")
    
    def show_history(self):
        """Show detection history"""
        print("\n" + "="*50)
        print("📋 DETECTION HISTORY")
        print("="*50)
        for i, item in enumerate(self.conversation_history[-5:], 1):  # Last 5 items
            status = "🚨" if item['prediction'] == 'ABUSIVE' else "✅"
            print(f"{i}. {status} {item['text']} ({item['confidence']:.1%})")
        print("="*50 + "\n")
    
    def show_summary(self):
        """Show session summary"""
        if self.conversation_history:
            abusive_count = sum(1 for item in self.conversation_history if item['prediction'] == 'ABUSIVE')
            total_count = len(self.conversation_history)
            print(f"\n📊 SESSION SUMMARY:")
            print(f"Total detections: {total_count}")
            print(f"Abusive content: {abusive_count}")
            print(f"Normal content: {total_count - abusive_count}")

# For direct script execution
if __name__ == "__main__":
    detector = ContinuousMalayalamDetector()
    detector.start_continuous_detection()