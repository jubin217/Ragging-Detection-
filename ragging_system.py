# ragging_system.py
import time
from decision_engine import DecisionEngine
from fight_module import FightDetector
from hate_module import HateDetector

fight = FightDetector()
hate = HateDetector()
engine = DecisionEngine()

fight.start()
hate.start()

print("🚀 Ragging Detection System Running")

while True:
    signals = {}
    signals.update(fight.get_state())
    signals.update(hate.get_state())

    state = engine.evaluate(signals)

    print("SYSTEM STATUS:", state)

    time.sleep(0.5)
