#!/bin/bash

# --- 1. CONFIGURATION ---
PC_MODEL_PATH="/mnt/d/GoogleDriveMirror/UNI/Thesis/Files/script/models/qwen2-0_5b-instruct-q4_k_m.gguf"
PHONE_WORKDIR="/data/local/tmp"
PHONE_MODEL="model.gguf"
PHONE_EXE="llama-cli"

# --- 2. CREATE FIXED PYTHON SCRIPT ---
echo "Creating analysis script..."
cat << 'EOF' > analyze_perfetto.py
from perfetto.trace_processor import TraceProcessor
import sys
import os
import bisect

# POWER TABLES (Samsung S25 Ultra)
POWER_PROFILE_0 = {
    384000: 85, 556800: 120, 748800: 165, 960000: 230,
    1152000: 320, 1363200: 440, 1555200: 580, 1785600: 750,
    1996800: 950, 2227200: 1200, 2400000: 1450, 2745600: 1900,
    2918400: 2150, 3072000: 2350, 3321600: 2500, 3532800: 2600
}
POWER_PROFILE_6 = {
    1017600: 380, 1209600: 480, 1401600: 620, 1689600: 800,
    1958400: 1050, 2246400: 1300, 2438400: 1600, 2649600: 1950,
    2841600: 2300, 3072000: 2700, 3283200: 3100, 3513600: 3450,
    3840000: 3750, 4089600: 3950, 4281600: 4100, 4473600: 4200
}

def analyze_trace(trace_path):
    abs_path = os.path.abspath(trace_path)
    if not os.path.exists(abs_path):
        print(f"[ERROR] Trace file not found: {abs_path}")
        return

    print(f"Loading trace from: {abs_path}")
    tp = TraceProcessor(trace=abs_path)
    
    # query slices
    slice_query = """
    SELECT s.ts, s.dur, s.cpu, p.name
    FROM sched_slice s
    JOIN thread t ON s.utid = t.utid
    JOIN process p ON t.upid = p.upid
    WHERE p.name LIKE '%llama%' 
    ORDER BY s.ts
    """
    
    # query frequency
    freq_query = """
    SELECT c.ts, c.value, t.cpu
    FROM counter c
    JOIN cpu_counter_track t ON c.track_id = t.id
    WHERE t.name = 'cpufreq'
    ORDER BY c.ts
    """
    
    slices = list(tp.query(slice_query))
    freqs = list(tp.query(freq_query))
    
    if not slices:
        print("\n[ERROR] No 'llama' process found!")
        return

    freq_map = {}
    for row in freqs:
        if row.cpu not in freq_map: freq_map[row.cpu] = {'ts': [], 'val': []}
        freq_map[row.cpu]['ts'].append(row.ts)
        freq_map[row.cpu]['val'].append(row.value)

    total_energy_joules = 0.0
    
    for s in slices:
        cpu = s.cpu
        start_ts = s.ts
        duration_sec = s.dur / 1e9
        
        current_freq = 0
        if cpu in freq_map:
            idx = bisect.bisect_right(freq_map[cpu]['ts'], start_ts) - 1
            if idx >= 0:
                current_freq = freq_map[cpu]['val'][idx]
        
        power_mw = 0
        if cpu < 6:
            power_mw = POWER_PROFILE_0.get(current_freq, 85)
        else:
            power_mw = POWER_PROFILE_6.get(current_freq, 380)
            
        # FIX: Directly calculate Joules. 
        # Power (Watts) = mW / 1000
        # Energy (Joules) = Watts * Seconds
        energy_joules = (power_mw / 1000.0) * duration_sec
        total_energy_joules += energy_joules

    print(f"\n[SUCCESS] Total Energy: {total_energy_joules:.4f} Joules")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python analyze_perfetto.py <trace_file>")
    else:
        analyze_trace(sys.argv[1])
EOF

# --- 3. PREPARE DEVICE ---
echo "Checking model..."
adb shell "ls $PHONE_WORKDIR/$PHONE_MODEL" > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "Pushing model..."
    adb push "$PC_MODEL_PATH" "$PHONE_WORKDIR/$PHONE_MODEL"
fi
adb shell "chmod +x $PHONE_WORKDIR/$PHONE_EXE"

# --- 4. START REAL WORKLOAD ---
echo "Starting Llama Inference..."
adb shell "pkill -f llama"

# Running Deterministic Mode (--temp 0) to reduce randomness
adb shell "cd $PHONE_WORKDIR && LD_LIBRARY_PATH=. ./$PHONE_EXE \
    -m $PHONE_MODEL \
    -p 'Explain quantum physics' \
    -n 300 \
    -t 8 \
    --temp 0 \
    --ignore-eos" > /dev/null 2>&1 &

echo "Waiting 2 seconds for warm up..."
sleep 2

# --- 5. RECORD PERFETTO ---
echo "Recording Power Trace (10 seconds)..."
adb shell "perfetto -c - --txt -o /data/misc/perfetto-traces/real_test.trace" <<EOF
duration_ms: 10000
buffers: {
    size_kb: 63488
    fill_policy: RING_BUFFER
}
data_sources: {
    config {
        name: "linux.process_stats"
        target_buffer: 0
        process_stats_config { scan_all_processes_on_start: true }
    }
}
data_sources: {
    config {
        name: "linux.ftrace"
        ftrace_config {
            ftrace_events: "power/cpu_frequency"
            ftrace_events: "sched/sched_switch"
            compact_sched: { enabled: true }
        }
    }
}
EOF

# --- 6. ANALYZE ---
echo "Pulling trace..."
kill $! 2>/dev/null
adb shell "pkill -f llama"
adb pull /data/misc/perfetto-traces/real_test.trace real_test.trace > /dev/null 2>&1

echo "Analyzing..."
python3 analyze_perfetto.py real_test.trace
rm analyze_perfetto.py
echo "Done."