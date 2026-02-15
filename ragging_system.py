# ragging_system.py
import time
from decision_engine import DecisionEngine
from fight_module import FightDetector
from hate_module import HateDetector
from colorama import Fore, Style, init

init(autoreset=True)

# -----------------------------------
# Initialize modules
# -----------------------------------
fight = FightDetector()
hate = HateDetector()
engine = DecisionEngine()

fight.start()
hate.start()

print(Fore.CYAN + "🚀 Ragging Detection System Running\n")

previous_state = None

# -----------------------------------
# MAIN LOOP
# -----------------------------------
while True:
    signals = {}
    signals.update(fight.get_state())
    signals.update(hate.get_state())

    state = engine.evaluate(signals)

    # -----------------------------------
    # Print only when state changes
    # -----------------------------------
    if state != previous_state:

        print("\n==================================================")

        if state == "EMERGENCY":
            print(Fore.RED + Style.BRIGHT +
                  "🚨🚨🚨  EMERGENCY DETECTED  🚨🚨🚨")
            print(Fore.RED + Style.BRIGHT +
                  "Immediate action required!")

        elif state == "WARNING":
            print(Fore.YELLOW + Style.BRIGHT +
                  "⚠️  WARNING: Suspicious Activity")

        else:
            print(Fore.GREEN + "✅ SYSTEM NORMAL")

        print("==================================================\n")

        previous_state = state

    # -----------------------------------
    # Always show detailed debug info
    # -----------------------------------
    print("----------------------------------------")
    print(f"📷 YOLO: {signals.get('yolo_violence', False)}")
    print(f"🦴 Pose Aggressive: {signals.get('pose_aggressive', False)}")
    print(f"🌊 Sudden Motion: {signals.get('sudden_motion', False)}")
    print(f"🎤 Last Voice: {signals.get('last_text', '')}")
    print(f"🗣 Hate Result: {signals.get('last_result', '')}")
    print(f"🧠 SYSTEM STATUS: {state}")
    print("----------------------------------------")

    time.sleep(0.5)
