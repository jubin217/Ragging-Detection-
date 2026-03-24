import serial
import time
import json
import os
import threading

CREDENTIALS_FILE = "pi_credentials.json"

class GSMNotifier:
    def __init__(self, port="/dev/ttyS0", baudrate=9600):
        self.port = port
        self.baudrate = baudrate
        self.numbers = ["8891136561", "9645429211", "9947034644"]
        
        # Load location from credentials
        self.location = "Unknown Campus"
        if os.path.exists(CREDENTIALS_FILE):
            try:
                with open(CREDENTIALS_FILE, 'r') as f:
                    creds = json.load(f)
                self.location = creds.get("location", "Unknown Campus")
            except Exception as e:
                print(f"⚠️ GSM init warning: {e}")
                
    def _send_sms_routine(self, message):
        print("📱 Initializing SIM800L for SMS broadcast...")
        try:
            # open serial
            ser = serial.Serial(self.port, self.baudrate, timeout=1)
            # send AT commands
            ser.write(b'AT\r')
            time.sleep(1)
            ser.write(b'AT+CMGF=1\r') # Text mode
            time.sleep(1)
            
            for number in self.numbers:
                ser.write(f'AT+CMGS="{number}"\r'.encode())
                time.sleep(1)
                ser.write(f'{message}\x1A'.encode()) # \x1A is CTRL+Z
                time.sleep(3) # wait for send
                print(f"✅ SMS sent to {number} via GSM.")
            ser.close()
        except Exception as e:
            print(f"❌ GSM Error: Failed to send SMS via {self.port}: {e}")

    def trigger_sms(self, alert_type):
        """Asynchronously dispatches SMS to all registered numbers."""
        message = f"ResQvoice ALERT: {alert_type} detected at {self.location}."
        threading.Thread(target=self._send_sms_routine, args=(message,), daemon=True).start()

# For local testing
if __name__ == "__main__":
    notifier = GSMNotifier()
    notifier.trigger_sms("TEST EVENT")
