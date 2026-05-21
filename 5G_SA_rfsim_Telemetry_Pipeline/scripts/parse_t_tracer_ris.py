#!/usr/bin/env python3
import struct
import sys
import os
import time
import numpy as np

# ======================================================================
# PRECISION XAPP (SRS + RAW IQ EXPORTER & POSITIONING)
# ======================================================================
# Parses binary data from 'record' tool (T-tracer format)
# Specifically optimized for OAI rfsimulator mode (Event IDs 0 and 1)
# ----------------------------------------------------------------------

FILE_PATH = "/home/beam/.gemini/tmp/demo/L1_metrics_RIS.raw"

ID_METRICS = 0 # GNB_PHY_L1_METRICS_RIS
ID_SRS = 1     # GNB_PHY_SRS_ESTIMATES_RIS

SAMPLING_RATE = 46.08e6
SPEED_OF_LIGHT = 299792458.0

# Throttle settings for visual dashboard
LAST_PRINT_TIME = 0.0
PRINT_INTERVAL = 0.25 if sys.stdout.isatty() else 2.0  # Dynamic throttling for logs

def estimate_rtt_and_extract_iq(srs_buffer, ant_idx, port_idx, ue_id):
    try:
        # 1. Convert byte buffer to complex numbers
        # OAI c16_t is [real (int16), imag (int16)]
        raw_data = np.frombuffer(srs_buffer, dtype=np.int16)
        complex_data = raw_data[0::2] + 1j * raw_data[1::2]
        
        # 2. RTT Calculation via IFFT (Precision Peak Detection)
        time_domain = np.fft.ifft(complex_data)
        peak_idx = np.argmax(np.abs(time_domain))
        
        # Normalize index to positive delay
        dist_m = ((peak_idx / SAMPLING_RATE) * SPEED_OF_LIGHT) / 2.0
        
        # 3. Calculate signal metrics directly from I/Q
        avg_mag = np.mean(np.abs(complex_data))
        avg_power = np.mean(np.square(np.abs(complex_data)))
        
        # Estimate RSRP in dBm (scaled for rfsimulator context)
        rsrp_dbm = 10.0 * np.log10(avg_power + 1e-10) - 50.0
        # Estimate SNR based on signal peak-to-average power ratio (PAPR)
        papr = np.max(np.square(np.abs(complex_data))) / (avg_power + 1e-10)
        snr_db = int(np.clip(10.0 * np.log10(papr + 1e-10), 5, 28))
        
        # Extract first 3 IQ samples (normalized)
        first_3 = complex_data[:3]
        iq_str = ", ".join([f"{c.real/32768.0:+.4f}{c.imag/32768.0:+.4f}j" for c in first_3])
        
        return dist_m, rsrp_dbm, snr_db, avg_mag, iq_str
    except Exception as e:
        return 0.0, -140.0, 0, 0.0, "0.0000+0.0000j"

def print_spatial_dashboard(ue_id, dist_ta, dist_rtt, rsrp_dbm, snr_db, beam_id, avg_mag, iq_str):
    global LAST_PRINT_TIME
    current_time = time.time()
    if current_time - LAST_PRINT_TIME < PRINT_INTERVAL:
        return  # Throttle terminal output
        
    LAST_PRINT_TIME = current_time
    
    # Clear screen only if running in an interactive terminal
    if sys.stdout.isatty():
        os.system('clear')
    else:
        print(f"\n--- [SPATIAL UPDATE @ {time.strftime('%H:%M:%S')}] ---")
    
    print("=" * 68)
    print(" 📡           O-RAN SRS REAL-TIME SPATIAL POSITIONING           📡")
    print("=" * 68)
    print(f" 👤 UE RNTI:          0x{ue_id:04X}")
    print(f" 🎯 RTT Distance:     {dist_rtt:.2f} m (From raw SRS I/Q via IFFT)")
    if dist_ta > 0:
        print(f" 📍 TA Distance:      {dist_ta:.2f} m")
    else:
        print(f" 📍 TA Distance:      Calculating...")
    print(f" 📶 Estimated RSRP:   {rsrp_dbm:.1f} dBm")
    print(f" 🌟 Estimated SNR:    {snr_db} dB")
    print(f" ⚡ Avg IQ Magnitude: {avg_mag:.2f}")
    print(f" 🔮 First 3 IQ Norm:  [{iq_str}]")
    print("-" * 68)
    
    # Draw responsive ascii space map
    map_length = 40
    # Map range up to 100m for simulation
    pos = min(int((dist_rtt / 100.0) * map_length), map_length - 1)
    sig_sym = "🟢" if rsrp_dbm >= -85 else "🟡" if rsrp_dbm >= -100 else "🔴"
    
    ascii_map = ["-"] * map_length
    if pos >= 0:
        ascii_map[pos] = sig_sym
        
    print("  [gNB] " + "".join(ascii_map) + f" [UE] ({dist_rtt:.1f} meters)")
    print("=" * 68)
    print(" Tip: Run a data plane test (e.g. ping) to stimulate active telemetry.")
    sys.stdout.flush()

def run_xapp():
    print(f"Monitoring Throttled PHY Telemetry in {FILE_PATH}...")
    if not os.path.exists(FILE_PATH):
        # Touch file
        with open(FILE_PATH, 'a'):
            os.utime(FILE_PATH, None)
        
    last_metrics = {}
    with open(FILE_PATH, "rb") as f:
        # Start from the absolute beginning of the file to guarantee correct record boundary alignment
        f.seek(0)
        print(f"Initial Sync Complete. Starting parsing from the beginning of {FILE_PATH}...")
        
        buffer = b""
        while True:
            chunk = f.read(65536)
            if not chunk:
                # Clear EOF flag to read appended data
                f.seek(f.tell())
                time.sleep(0.05)
                continue
                
            buffer += chunk
            while len(buffer) >= 24: # Header size (4B len + 16B time + 4B ID)
                try:
                    ev_len = struct.unpack("I", buffer[0:4])[0]
                    if ev_len > 3000000 or ev_len == 0:
                        buffer = buffer[1:]
                        continue
                    if len(buffer) < (4 + ev_len): break
                    
                    event = buffer[4 : 4 + ev_len]
                    buffer = buffer[4 + ev_len:]
                    
                    ev_id = struct.unpack("I", event[16:20])[0] # ID at offset 20 in buffer
                    payload = event[20:]
                    
                    if ev_id == ID_METRICS:
                        # int,ue_id : float,distance_m : float,rsrp_dbm : float,snr_db : int,beam_id
                        if len(payload) >= 20:
                            ue_id, dist_ta, rsrp, snr, beam_id = struct.unpack("iffii", payload)
                            rtt_val = last_metrics.get(ue_id, {}).get('rtt', 0.0)
                            avg_mag = last_metrics.get(ue_id, {}).get('mag', 0.0)
                            iq_str = last_metrics.get(ue_id, {}).get('iq', "N/A")
                            print_spatial_dashboard(ue_id, dist_ta, rtt_val, rsrp, snr, beam_id, avg_mag, iq_str)
                            last_metrics[ue_id] = {'ta': dist_ta, 'rtt': rtt_val, 'mag': avg_mag, 'iq': iq_str}
                        
                    elif ev_id == ID_SRS:
                        # int,ue_id : int,ant_idx : int,port_idx : buffer,estimates
                        if len(payload) >= 12:
                            ue_id, ant, port = struct.unpack("iii", payload[:12])
                            rtt_dist, rsrp_dbm, snr_db, avg_mag, iq_str = estimate_rtt_and_extract_iq(payload[12:], ant, port, ue_id)
                            
                            # Keep track of metrics
                            if ue_id not in last_metrics:
                                last_metrics[ue_id] = {'ta': 0.0, 'rtt': rtt_dist, 'mag': avg_mag, 'iq': iq_str}
                            else:
                                last_metrics[ue_id]['rtt'] = rtt_dist
                                last_metrics[ue_id]['mag'] = avg_mag
                                last_metrics[ue_id]['iq'] = iq_str
                                
                            # Since we don't have ID_METRICS in monolithic mode, print dashboard directly from SRS!
                            ta_val = last_metrics[ue_id].get('ta', 0.0)
                            print_spatial_dashboard(ue_id, ta_val, rtt_dist, rsrp_dbm, snr_db, 0, avg_mag, iq_str)
                                
                except Exception as e:
                    # Skip corrupt bytes
                    buffer = buffer[1:]

if __name__ == "__main__":
    try:
        run_xapp()
    except KeyboardInterrupt:
        print("\nxApp Stopped.")
