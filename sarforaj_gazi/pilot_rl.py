import asyncio
import websockets
import json
import re
import random
import pickle
import os
from collections import defaultdict

QTABLE_FILE = "qtable.pkl"
ACTIONS = [
    {"speed": s, "altitude": a, "movement": "fwd"}
    for s in range(1, 6)
    for a in [-1, 0, 1]
]
EPSILON = 0.1  # Exploration rate
ALPHA = 0.1    # Learning rate
GAMMA = 0.9    # Discount factor

q_table = defaultdict(float)

# Load Q-table if exists
if os.path.exists(QTABLE_FILE):
    with open(QTABLE_FILE, 'rb') as f:
        q_table = pickle.load(f)

def parse_telemetry(raw):
    match = re.search(
        r"X-(?P<x>-?\d+)-Y-(?P<y>-?\d+)-BAT-(?P<battery>[-+]?\d*\.?\d+)"
        r"-GYR-\[(?P<gx>[^,]+),(?P<gy>[^,]+),(?P<gz>[^\]]+)\]"
        r"-WIND-(?P<wind>[-+]?\d*\.?\d+)-DUST-(?P<dust>[-+]?\d*\.?\d+)"
        r"-SENS-(?P<sensor>\w+)",
        raw
    )
    if match:
        g = match.groupdict()
        return {
            "x": int(g["x"]),
            "y": int(g["y"]),
            "battery": float(g["battery"]),
            "gx": float(g["gx"]),
            "gy": float(g["gy"]),
            "gz": float(g["gz"]),
            "wind": float(g["wind"]),
            "dust": float(g["dust"]),
            "sensor": g["sensor"].upper()
        }
    return None

def get_state(telemetry):
    # Simplify state space to avoid large Q-table
    y_bin = int(telemetry['y'] // 100)
    bat_bin = int(telemetry['battery'] // 10)
    tilt = int((telemetry['gx'] ** 2 + telemetry['gy'] ** 2) ** 0.5)
    tilt_bin = int(tilt // 10)
    sensor = telemetry['sensor']
    return (y_bin, bat_bin, tilt_bin, sensor)

def get_reward(metrics, crashed):
    if crashed:
        return -100
    return metrics.get("total_distance", 0)

def choose_action(state):
    if random.random() < EPSILON:
        return random.randint(0, len(ACTIONS) - 1)
    return max(range(len(ACTIONS)), key=lambda a: q_table[state][a])

async def smart_pilot_rl():
    uri = "ws://localhost:8765"
    async with websockets.connect(uri) as websocket:
        print("[RL-PILOT CONNECTED]")

        local_iterations = 0
        last_state = None
        last_action = None

        await websocket.send(json.dumps({"speed": 1, "altitude": 1, "movement": "fwd"}))

        while True:
            try:
                data = await websocket.recv()
                response = json.loads(data)
                metrics = response.get("metrics", {})
                telemetry_raw = response.get("telemetry", "")

                if response.get("status") == "crashed":
                    reward = get_reward(metrics, crashed=True)
                    if last_state is not None and last_action is not None:
                        q_table[last_state][last_action] += ALPHA * (
                            reward - q_table[last_state][last_action]
                        )
                    print("[CRASHED] Reward:", reward)
                    break

                telemetry = parse_telemetry(telemetry_raw)
                if not telemetry:
                    continue

                state = get_state(telemetry)
                action_index = choose_action(state)
                action = ACTIONS[action_index]

                reward = get_reward(metrics, crashed=False)

                if last_state is not None and last_action is not None:
                    best_next = max(q_table[state])
                    q_table[last_state][last_action] += ALPHA * (
                        reward + GAMMA * best_next - q_table[last_state][last_action]
                    )

                last_state = state
                last_action = action_index

                await websocket.send(json.dumps(action))
                local_iterations += 1
                await asyncio.sleep(0.5)

            except Exception as e:
                print("[ERROR]", e)
                break

    # Save updated Q-table
    with open(QTABLE_FILE, 'wb') as f:
        pickle.dump(q_table, f)

if __name__ == "__main__":
    asyncio.run(smart_pilot_rl())
