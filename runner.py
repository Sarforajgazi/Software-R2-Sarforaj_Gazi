import asyncio
import subprocess
import json
import os
import signal
import matplotlib.pyplot as plt

RUNS = 5
LOG_FILE = "crash_log.json"
RESPONSES_FILE = "last_responses.json"
SERVER_SCRIPT = "run_server.py"
PILOT_SCRIPT = "sarforaj_gazi/pilot.py"


iterations_data = []
crash_reasons = []
last_responses = []
distances = []

async def launch_server():
    return await asyncio.create_subprocess_exec(
        "python", SERVER_SCRIPT,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL
    )

async def kill_process(proc):
    if proc and proc.returncode is None:
        proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), timeout=3)
        except asyncio.TimeoutError:
            proc.kill()

async def run_pilot():
    proc = await asyncio.create_subprocess_exec(
        "python3", PILOT_SCRIPT, 
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    if stderr:
        print("Pilot Error:", stderr.decode())

    out_lines = stdout.decode().splitlines()
    iter_count = 0
    reason = "Unknown"
    distance = 0.0
    last_response = {}

    for line in out_lines:
        if "[LOCAL ITERATIONS]:" in line:
            iter_count = int(line.split(":")[-1].strip())
        elif "[CRASH]" in line:
            reason = line.strip()
        elif "[RAW DATA]:" in line:
            try:
                last_response = json.loads(line.replace("[RAW DATA]:", "").strip())
                metrics = last_response.get("metrics", {})
                distance = float(metrics.get("total_distance", 0))
            except json.JSONDecodeError:
                pass

    return iter_count, reason, distance, last_response

async def run_all():
    print(f"Running {RUNS} test simulations...\n")

    for i in range(RUNS):
        print(f"--- Run {i + 1} ---")

        server_proc = await launch_server()
        await asyncio.sleep(1.5)  # Wait for server to boot up

        iter_count, reason, distance, last_response = await run_pilot()
        await kill_process(server_proc)

        iterations_data.append(iter_count)
        crash_reasons.append(reason)
        distances.append(distance)
        last_responses.append(last_response)

        print(f"Iterations: {iter_count}, Distance: {distance:.2f}, Reason: {reason}")

    with open(LOG_FILE, "w") as f:
        json.dump({"iterations": iterations_data, "reasons": crash_reasons, "distances": distances}, f, indent=2)

    with open(RESPONSES_FILE, "w") as f:
        json.dump(last_responses, f, indent=2)

    avg_iterations = sum(iterations_data) / len(iterations_data)
    avg_distance = sum(distances) / len(distances)
    print(f"\nAverage Iterations: {avg_iterations:.2f}")
    print(f"Average Distance: {avg_distance:.2f} meters")

    plot_iterations()
    plot_distances()

def plot_iterations():
    plt.figure(figsize=(10, 5))
    plt.plot(range(1, RUNS + 1), iterations_data, marker='o', label="Iterations before crash")
    plt.axhline(sum(iterations_data) / RUNS, color='r', linestyle='--', label="Average Iterations")
    plt.xlabel("Simulation Run")
    plt.ylabel("Iterations")
    plt.title("Drone Simulation Iterations Before Crash")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig("iteration_plot.png")
    plt.show()

def plot_distances():
    plt.figure(figsize=(10, 5))
    plt.plot(range(1, RUNS + 1), distances, marker='s', color='green', label="Distance before crash")
    plt.axhline(sum(distances) / RUNS, color='orange', linestyle='--', label="Average Distance")
    plt.xlabel("Simulation Run")
    plt.ylabel("Distance (meters)")
    plt.title("Distance Covered Before Crash")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig("distance_plot.png")
    plt.show()

if __name__ == "__main__":
    asyncio.run(run_all())
