import requests
import json
import time
import os
import urllib.parse

# Firebase configuration from the user
FIREBASE_CONFIG = {
  "apiKey": "AIzaSyBxBla4ND-cpMTt5ifCpdhutFqTy1RXT8M",
  "projectId": "raggingsystem",
}

CREDENTIALS_FILE = "pi_credentials.json"

class FirebaseLogger:
    def __init__(self):
        self.id_token = None
        self.refresh_token = None
        self.token_expiry = 0
        self.local_id = None # User UID
        self._load_credentials()
        self._authenticate()

    def _load_credentials(self):
        if not os.path.exists(CREDENTIALS_FILE):
            default_creds = {
                "email": "pi1@raggingsystem.com",
                "password": "password123",
                "location": "Main Campus - CS Block"
            }
            with open(CREDENTIALS_FILE, 'w') as f:
                json.dump(default_creds, f, indent=4)
            print(f"⚠️ Created {CREDENTIALS_FILE}. Please edit it with real auth credentials.")

    def _authenticate(self):
        """Signs in to Firebase Auth to get an ID token."""
        if not os.path.exists(CREDENTIALS_FILE):
            return
            
        with open(CREDENTIALS_FILE, 'r') as f:
            creds = json.load(f)
            
        url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_CONFIG['apiKey']}"
        payload = {
            "email": creds.get("email", ""),
            "password": creds.get("password", ""),
            "returnSecureToken": True
        }
        try:
            response = requests.post(url, json=payload)
            if response.status_code == 200:
                data = response.json()
                self.id_token = data['idToken']
                self.refresh_token = data['refreshToken']
                self.local_id = data['localId']
                self.token_expiry = time.time() + int(data['expiresIn'])
                print(f"✅ Pi Network Authenticated | Device Identity: {self.local_id}")
            else:
                print(f"⚠️ Auth Failed: {response.json().get('error', {}).get('message', 'Unknown error')}")
                print(f"📝 Note: Ensure {CREDENTIALS_FILE} has a valid Firebase registered user account.")
        except Exception as e:
            print(f"❌ Connection Error: {e}")

    def _ensure_token(self):
        """Refreshes the token if it's expired."""
        if time.time() > self.token_expiry - 60: # 1 minute buffer
            self._authenticate()

    def log_alert(self, alert_type, is_emergency=True, evidence_url=None):
        """Pushes an alert to the unique user's Firestore subcollection."""
        self._ensure_token()
        if not self.id_token or not self.local_id:
            print("❌ Cannot log alert: Pi is not authenticated")
            return

        with open(CREDENTIALS_FILE, 'r') as f:
            creds = json.load(f)
            location = creds.get("location", "Unknown Campus")

        # Isolated data path: users/{uid}/alerts/
        url = f"https://firestore.googleapis.com/v1/projects/{FIREBASE_CONFIG['projectId']}/databases/(default)/documents/users/{self.local_id}/alerts"
        headers = {"Authorization": f"Bearer {self.id_token}"}
        
        payload = {
            "fields": {
                "type": {"stringValue": alert_type},
                "location": {"stringValue": location},
                "isEmergency": {"booleanValue": is_emergency},
                "acknowledged": {"booleanValue": False},
                "timestamp": {"timestampValue": f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}"}
            }
        }
        
        if evidence_url:
            payload["fields"]["evidenceUrl"] = {"stringValue": evidence_url}

        try:
            response = requests.post(url, headers=headers, json=payload)
            if response.status_code == 200:
                print(f"🚀 Alert pushed securely to Dashboard: {alert_type}")
            else:
                print(f"⚠️ Firestore Push Failed: {response.text}")
        except Exception as e:
            print(f"❌ Error logging to Firebase: {e}")

    def _upload_evidence(self, frame_path):
        """Uploads a frame to Firebase Storage using REST API and returns download URL."""
        self._ensure_token()
        if not self.id_token:
            return None
        
        filename = os.path.basename(frame_path)
        encoded_name = urllib.parse.quote(f"evidence/{filename}", safe='')
        
        bucket = f"{FIREBASE_CONFIG['projectId']}.firebasestorage.app"
        url = f"https://firebasestorage.googleapis.com/v0/b/{bucket}/o?name={encoded_name}"
        headers = {
            "Authorization": f"Bearer {self.id_token}",
            "Content-Type": "image/jpeg"
        }
        
        try:
            with open(frame_path, "rb") as f:
                data = f.read()
            response = requests.post(url, headers=headers, data=data)
            if response.status_code == 200:
                resp_json = response.json()
                token = resp_json.get("downloadTokens")
                if token:
                    download_url = f"https://firebasestorage.googleapis.com/v0/b/{bucket}/o/{encoded_name}?alt=media&token={token}"
                    print(f"📸 Evidence uploaded securely to Cloud Storage!")
                    return download_url
            else:
                print(f"⚠️ Evidence upload failed: {response.text}")
        except Exception as e:
            print(f"❌ Error uploading evidence: {e}")
            
        return None

    def log_with_evidence(self, alert_type, is_emergency, frame_path):
        """Uploads evidence then logs the alert immediately."""
        evidence_url = None
        if os.path.exists(frame_path):
            evidence_url = self._upload_evidence(frame_path)
            try:
                os.remove(frame_path) # Cleanup temporary file
            except Exception as e:
                print(f"⚠️ Failed to remove temp evidence file: {e}")
                
        self.log_alert(alert_type, is_emergency, evidence_url)

if __name__ == "__main__":
    logger = FirebaseLogger()
    logger.log_alert("TEST ALERT (Device Init)", True)
