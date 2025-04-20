import asyncio
import websockets
import json
import re
import math

MAX_X_RANGE = 100000
CRITICAL_TILT_DEGREES = 45
DEGREES_TO_GYRO = 1/90
ALTITUDE_LIMITS = {
    "GREEN": 5000,
    "YELLOW": 999,
    "RED": 2
}

def parse_telemetry(raw: str):
    match = re.search(
        r"X-(?P<x>-?\d+)-Y-(?P<y>-?\d+)-BAT-(?P<battery>[-+]?\d*\.?\d+)"
        r"-GYR-\[(?P<gx>[^,]+),(?P<gy>[^,]+),(?P<gz>[^\]]+)\]"
        r"-WIND-(?P<wind>[-+]?\d*\.?\d+)-DUST-(?P<dust>[-+]?\d*\.?\d+)"
        r"-SENS-(?P<sensor>\w+)",
        raw
    )
    if match:
        groups = match.groupdict()
        return {
            "x": int(groups["x"]),
            "y": int(groups["y"]),
            "battery": float(groups["battery"]),
            "gx": float(groups["gx"]),
            "gy": float(groups["gy"]),
            "gz": float(groups["gz"]),
            "wind": float(groups["wind"]),
            "dust": float(groups["dust"]),
            "sensor": groups["sensor"]
        }
    return None

async def smart_pilot():
    uri = "ws://localhost:8765"
    async with websockets.connect(uri) as websocket:
        print("[CONNECTED TO SERVER]")

        await websocket.send(json.dumps({
            "speed": 1,
            "altitude": 1,
            "movement": "fwd"
        }))

        local_iterations = 0
        initial_battery = 100.0

        while True:
            try:
                data = await websocket.recv()
                print("[RAW DATA]:", data)

                response = json.loads(data)

                telemetry_raw = response.get("telemetry", "")
                print("[TELEMETRY RAW]:", telemetry_raw)

                metrics = response.get("metrics", {})
                status = response.get("status")

                if status == "crashed":
                    print("[CRASHED] Server Iterations:", metrics.get("iterations"))
                    print("[LOCAL ITERATIONS]:", local_iterations)
                    break

                telemetry = parse_telemetry(telemetry_raw)
                if not telemetry:
                    print("[Invalid telemetry]")
                    continue

                x = telemetry["x"]
                y = telemetry["y"]
                battery = telemetry["battery"]
                gx = telemetry["gx"]
                gy = telemetry["gy"]
                sensor = telemetry["sensor"].upper()

                # Calculate tilt in degrees
                tilt_magnitude = math.sqrt(gx**2 + gy**2)
                tilt_degrees = tilt_magnitude / DEGREES_TO_GYRO

                # === EMERGENCY CRASH CHECKS ===
                unsafe_sensor_altitude = (
                    (sensor == "RED" and y >= 3) or
                    (sensor == "YELLOW" and y >= 1000)
                )

                if battery <= 0:
                    print("[CRASH] Battery depleted")
                if y < 0:
                    print("[CRASH] Ground collision")
                if abs(x) > MAX_X_RANGE:
                    print("[CRASH] Range exceeded")
                if tilt_degrees > CRITICAL_TILT_DEGREES:
                    print(f"[CRASH] Excessive tilt: {tilt_degrees:.2f}° > {CRITICAL_TILT_DEGREES}°")
                if unsafe_sensor_altitude:
                    print(f"[CRASH] Unsafe altitude for {sensor} sensor: y={y}")

                if (battery <= 0 or y < 0 or abs(x) > MAX_X_RANGE 
                    or tilt_degrees > CRITICAL_TILT_DEGREES or unsafe_sensor_altitude):
                    print("[EMERGENCY LANDING]")
                    command = {"speed": 0, "altitude": -1, "movement": "rev"}
                else:
                    max_altitude = ALTITUDE_LIMITS.get(sensor, 5000)

                    if y < 3:
                        altitude = 1
                    elif y > max_altitude:
                        altitude = -1
                    elif tilt_degrees > 35:
                        altitude = 1
                    else:
                        altitude = 0

                    if battery > 75:
                        speed = 5
                    elif battery > 50:
                        speed = 4
                    elif battery > 30:
                        speed = 3
                    elif battery > 15:
                        speed = 2
                    else:
                        speed = 1

                    altitude_factor = 1.0
                    if y < 100:
                        altitude_factor = 1.0 + (0.8 * (100 - y) / 100)
                    elif y > 1000:
                        altitude_factor = max(0.6, 1.0 - (0.4 * (y - 1000) / 4000))

                    base_drain = 0.1
                    battery_deduction = base_drain * speed * altitude_factor
                    battery = max(0, battery - battery_deduction)

                    if speed > 0 and altitude != 0:
                        local_iterations += 1

                    command = {
                        "speed": speed,
                        "altitude": altitude,
                        "movement": "fwd"
                    }

                await websocket.send(json.dumps(command))
                await asyncio.sleep(0.5)

            except websockets.ConnectionClosed as e:
                print("[Connection Closed]:", e)
                break
            except Exception as e:
                print("[Unhandled Exception]:", e)
                break

# Run the pilot
asyncio.run(smart_pilot())