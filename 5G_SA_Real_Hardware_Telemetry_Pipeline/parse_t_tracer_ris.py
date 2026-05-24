#!/usr/bin/env python3
import struct
import sys
import os
import time
import numpy as np

# ======================================================================
# PRECISION DUAL-RX XAPP (SRS MIMO + RAW IQ & PHASE EXPORTER)
# ======================================================================
# Parses binary data from 'record' tool (T-tracer format)
# Specifically optimized for OAI USRP B210 Dual-Antenna (MIMO RX0/RX1)
# ----------------------------------------------------------------------

FILE_PATH = "/home/beam/.gemini/tmp/demo/L1_metrics_RIS.raw"

ID_METRICS = 0 # GNB_PHY_L1_METRICS_RIS
ID_SRS = 1     # GNB_PHY_SRS_ESTIMATES_RIS

SAMPLING_RATE = 46.08e6
SPEED_OF_LIGHT = 299792458.0

# Throttle settings for visual dashboard
LAST_PRINT_TIME = 0.0
PRINT_INTERVAL = 0.25 if sys.stdout.isatty() else 2.0

# Buffering structures for MIMO (RX0 & RX1 alignment)
srs_mimo_buffer = {}

def estimate_rtt_and_extract_iq(srs_buffer):
    try:
        raw_data = np.frombuffer(srs_buffer, dtype=np.int16)
        if len(raw_data) < 2:
            return 0.0, -140.0, 0, 0.0, "N/A", "N/A", np.array([]), False
            
        complex_data = raw_data[0::2] + 1j * raw_data[1::2]
        
        # Calculate average power & magnitude
        avg_mag = np.mean(np.abs(complex_data))
        avg_power = np.mean(np.square(np.abs(complex_data)))
        
        # Active transmission threshold (Thermal Noise floor is typically ~300-380 on B210)
        # Tuned to 400.0 to accommodate RX0 fading on real B210 hardware
        srs_detected = avg_mag > 400.0
        
        if not srs_detected:
            first_3 = complex_data[:3]
            iq_str = ", ".join([f"{int(c.real):+d}{int(c.imag):+d}j" for c in first_3]) + " (Noise)"
            return 0.0, -120.0, 3, avg_mag, iq_str, "N/A", complex_data, False
            
        # 1. RTT via IFFT (with FFT Shift & Sub-sample Quadratic Interpolation)
        time_domain = np.fft.ifft(complex_data)
        N = len(time_domain)
        abs_td = np.abs(time_domain)
        peak_idx = np.argmax(abs_td)
        
        # Quadratic peak interpolation for sub-sample resolution (cm level accuracy)
        prev_idx = (peak_idx - 1) % N
        next_idx = (peak_idx + 1) % N
        
        y_prev = abs_td[prev_idx]
        y_peak = abs_td[peak_idx]
        y_next = abs_td[next_idx]
        
        denom = (y_prev - 2.0 * y_peak + y_next)
        if abs(denom) > 1e-5:
            frac = 0.5 * (y_prev - y_next) / denom
        else:
            frac = 0.0
            
        refined_peak = peak_idx + frac
        if refined_peak > N // 2:
            delay_samples = refined_peak - N
        else:
            delay_samples = refined_peak
            
        dist_m = ((delay_samples / SAMPLING_RATE) * SPEED_OF_LIGHT) / 2.0
            
        # 2. Calculate RSRP (with physical USRP B210 offset -10 dB)
        norm_power = avg_power / (32768.0 ** 2)
        rsrp_dbm = 10.0 * np.log10(norm_power + 1e-12) - 10.0  
        rsrp_dbm = np.clip(rsrp_dbm, -140.0, -10.0)
        
        # 3. Estimate Physical SNR directly from active subcarriers (first-order difference)
        active_samples = complex_data[np.abs(complex_data) > 10.0]
        if len(active_samples) > 5:
            diffs = np.diff(active_samples)
            noise_power = 0.5 * np.mean(np.square(np.abs(diffs)))
            total_power = np.mean(np.square(np.abs(active_samples)))
            signal_power = max(total_power - noise_power, 1e-10)
            snr_val = signal_power / (noise_power + 1e-10)
            snr_db = int(np.clip(10.0 * np.log10(snr_val), 1, 35))
        else:
            snr_db = 5
            
        # Extract middle 3 subcarriers (OFDM Guard Band bypass)
        mid_idx = len(complex_data) // 2
        middle_3 = complex_data[mid_idx : mid_idx + 3]
        iq_str = ", ".join([f"{int(c.real):+d}{int(c.imag):+d}j" for c in middle_3])
        
        full_iq_str = ";".join([f"{int(c.real):+d}{int(c.imag):+d}j" for c in complex_data])
        
        return dist_m, rsrp_dbm, snr_db, avg_mag, iq_str, full_iq_str, complex_data, True
    except Exception as e:
        return 0.0, -140.0, 0, 0.0, "Error", "N/A", np.array([]), False

def print_spatial_dashboard_mimo(ue_id, dist_ta, last_metrics):
    global LAST_PRINT_TIME
    current_time = time.time()
    if current_time - LAST_PRINT_TIME < PRINT_INTERVAL:
        return
        
    LAST_PRINT_TIME = current_time
    
    if sys.stdout.isatty():
        os.system('clear')
    else:
        print(f"\n--- [SPATIAL MIMO UPDATE @ {time.strftime('%H:%M:%S')}] ---")
        
    ue_data = last_metrics.get(ue_id, {})
    rx0 = ue_data.get('rx0', {})
    rx1 = ue_data.get('rx1', {})
    
    srs_detected = rx0.get('detected', False) or rx1.get('detected', False)
    phase_diff = ue_data.get('phase_diff_deg', 0.0)
    
    print("=" * 76)
    print(" 📡     O-RAN USRP B210 REAL HARDWARE SRS DUAL-RX SPATIAL MONITOR     📡")
    print("=" * 76)
    print(f" 👤 UE RNTI:          0x{ue_id:04X} ({ue_id})")
    
    if srs_detected:
        print(f" 📡 SRS Detection:    🟢 DETECTED (Active Dual-RX UL Transmission)")
    else:
        print(f" 📡 SRS Detection:    🟡 SEARCHING... (CPE Idle / Noise Floor)")
        
    print("-" * 76)
    # RX0 (Antenna 0) Stats
    print(f" 🎯 RX0 RTT Distance: {rx0.get('rtt', 0.0):+.2f} m | RSRP: {rx0.get('rsrp', -140.0):.1f} dBm | SNR: {rx0.get('snr', 0)} dB")
    print(f" 🔮 RX0 Middle 3 IQ:  [{rx0.get('iq_str', 'N/A')}]")
    
    # RX1 (Antenna 1) Stats
    print(f" 🎯 RX1 RTT Distance: {rx1.get('rtt', 0.0):+.2f} m | RSRP: {rx1.get('rsrp', -140.0):.1f} dBm | SNR: {rx1.get('snr', 0)} dB")
    print(f" 🔮 RX1 Middle 3 IQ:  [{rx1.get('iq_str', 'N/A')}]")
    
    print("-" * 76)
    # Physical Phase Difference for Angle of Arrival (AoA)
    if srs_detected and rx0.get('detected', False) and rx1.get('detected', False):
        print(f" 📐 Phase Diff (RX0-RX1): {phase_diff:+.2f}° (Physical Phase shift for AoA)")
    else:
        print(f" 📐 Phase Diff (RX0-RX1): N/A (Awaiting Dual-RX Coherent Samples)")
        
    if dist_ta != 0.0:
        print(f" 📍 Timing Advance Dist: {dist_ta:+.2f} m (From gNB MAC)")
    elif srs_detected:
        avg_rtt = (rx0.get('rtt', 0.0) + rx1.get('rtt', 0.0)) / 2.0
        print(f" 📍 Timing Advance Dist: {avg_rtt:+.2f} m (Estimated Average RTT)")
    else:
        print(f" 📍 Timing Advance Dist: Calculating...")
        
    print(f" ⚡ Avg Magnitude (0/1): {rx0.get('mag', 0.0):.1f} / {rx1.get('mag', 0.0):.1f} USRP ADC Level")
    print("=" * 76)
    
    # Responsive ascii space map for MIMO (up to 100 meters range)
    map_length = 35
    avg_dist = (rx0.get('rtt', 0.0) + rx1.get('rtt', 0.0)) / 2.0
    pos = max(0, min(int((avg_dist / 100.0) * map_length), map_length - 1)) if srs_detected else -1
    
    avg_rsrp = (rx0.get('rsrp', -140.0) + rx1.get('rsrp', -140.0)) / 2.0
    sig_sym = "🟢" if avg_rsrp >= -85 else "🟡" if avg_rsrp >= -105 else "🔴"
    
    ascii_map = ["-"] * map_length
    if pos >= 0:
        ascii_map[pos] = sig_sym
        
    map_str = "  [gNB] " + "".join(ascii_map)
    if srs_detected:
        map_str += f" [UE] (Avg RTT: {avg_dist:+.2f} m | Phase: {phase_diff:+.1f}°)"
    else:
        map_str += " [UE] (Scanning...)"
        
    print(map_str)
    print("=" * 76)
    print(" Tip: Trigger uplink data traffic (e.g. ping) from CPE to stimulate SRS telemetry.")
    sys.stdout.flush()

def run_xapp():
    print(f"Monitoring Dual-RX PHY Telemetry in {FILE_PATH}...")
    if not os.path.exists(FILE_PATH):
        with open(FILE_PATH, 'a'):
            os.utime(FILE_PATH, None)
            
    last_metrics = {}
    with open(FILE_PATH, "rb") as f:
        f.seek(0)
        print(f"Sync complete. Starting real-time parsing of {FILE_PATH}...")
        
        buffer = b""
        while True:
            chunk = f.read(65536)
            if not chunk:
                f.seek(f.tell())
                time.sleep(0.05)
                continue
                
            buffer += chunk
            while len(buffer) >= 24:
                try:
                    ev_len = struct.unpack("I", buffer[0:4])[0]
                    if ev_len > 3000000 or ev_len == 0:
                        buffer = buffer[1:]
                        continue
                    if len(buffer) < (4 + ev_len): 
                        break
                        
                    event = buffer[4 : 4 + ev_len]
                    buffer = buffer[4 + ev_len:]
                    
                    ev_id = struct.unpack("I", event[16:20])[0]
                    payload = event[20:]
                    
                    if ev_id == ID_METRICS:
                        if len(payload) >= 20:
                            ue_id, dist_ta, rsrp, snr, beam_id = struct.unpack("iffii", payload)
                            if ue_id in last_metrics:
                                # Display dashboard
                                print_spatial_dashboard_mimo(ue_id, dist_ta, last_metrics)
                                last_metrics[ue_id]['ta'] = dist_ta
                                last_metrics[ue_id]['rsrp_kpm'] = rsrp
                            
                    elif ev_id == ID_SRS:
                        if len(payload) >= 12:
                            ue_id, ant, port = struct.unpack("iii", payload[:12])
                            srs_signal = payload[16:]
                            
                            # Estimate physical metrics for this specific antenna
                            rtt_dist, rsrp_dbm, snr_db, avg_mag, iq_str, full_iq_str, complex_array, srs_det = estimate_rtt_and_extract_iq(srs_signal)
                            
                            # Initialize UE MIMO state
                            if ue_id not in last_metrics:
                                last_metrics[ue_id] = {
                                    'ta': 0.0,
                                    'rsrp_kpm': None,
                                    'phase_diff_deg': 0.0,
                                    'rx0': {'detected': False, 'rtt': 0.0, 'rsrp': -140.0, 'snr': 0, 'mag': 0.0, 'iq_str': "N/A", 'full_iq_str': "N/A", 'array': np.array([])},
                                    'rx1': {'detected': False, 'rtt': 0.0, 'rsrp': -140.0, 'snr': 0, 'mag': 0.0, 'iq_str': "N/A", 'full_iq_str': "N/A", 'array': np.array([])}
                                }
                                
                            ant_key = 'rx0' if ant == 0 else 'rx1'
                            last_metrics[ue_id][ant_key] = {
                                'detected': srs_det,
                                'rtt': rtt_dist,
                                'rsrp': rsrp_dbm,
                                'snr': snr_db,
                                'mag': avg_mag,
                                'iq_str': iq_str,
                                'full_iq_str': full_iq_str,
                                'array': complex_array
                            }
                            
                            # Coherent MIMO processing when we have both antennas aligned
                            rx0_data = last_metrics[ue_id]['rx0']
                            rx1_data = last_metrics[ue_id]['rx1']
                            
                            if rx0_data['detected'] and rx1_data['detected'] and len(rx0_data['array']) > 0 and len(rx1_data['array']) > 0:
                                # Calculate physical Phase Difference for AoA
                                # H = S0 * S1* (conjugate product per subcarrier)
                                min_len = min(len(rx0_data['array']), len(rx1_data['array']))
                                s0 = rx0_data['array'][:min_len]
                                s1 = rx1_data['array'][:min_len]
                                
                                # Conjugate multiplication and average vector phase angle
                                conj_product = s0 * np.conj(s1)
                                mean_vector = np.sum(conj_product)
                                mean_phase_rad = np.angle(mean_vector)
                                phase_diff_deg = np.degrees(mean_phase_rad)
                                
                                last_metrics[ue_id]['phase_diff_deg'] = phase_diff_deg
                                
                                # Save dual-channel aligned data to CSV dataset
                                if srs_det and ant == 1: # Log once per coherent pair (trigger on RX1)
                                    csv_file_path = "/home/beam/.gemini/tmp/demo/srs_dataset_real_hardware.csv"
                                    try:
                                        os.makedirs(os.path.dirname(csv_file_path), exist_ok=True)
                                        file_exists = os.path.exists(csv_file_path)
                                        
                                        ta_val = last_metrics[ue_id].get('ta', 0.0)
                                        if ta_val == 0.0:
                                            # Average RTT estimate
                                            ta_val = (rx0_data['rtt'] + rx1_data['rtt']) / 2.0
                                            
                                        with open(csv_file_path, "a") as csv_f:
                                            if not file_exists:
                                                # New beautiful dual-rx CSV structure
                                                csv_f.write("Timestamp,RNTI,RTT_Dist_RX0_m,RTT_Dist_RX1_m,TA_Distance_m,RSRP_RX0_dBm,RSRP_RX1_dBm,SNR_RX0_dB,SNR_RX1_dB,Phase_Diff_deg,Avg_Mag_RX0,Avg_Mag_RX1,Raw_IQ_Full_RX0,Raw_IQ_Full_RX1\n")
                                            
                                            timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
                                            csv_f.write(f"{timestamp},0x{ue_id:04X},"
                                                        f"{rx0_data['rtt']:+.4f},{rx1_data['rtt']:+.4f},{ta_val:+.4f},"
                                                        f"{rx0_data['rsrp']:.2f},{rx1_data['rsrp']:.2f},"
                                                        f"{rx0_data['snr']},{rx1_data['snr']},{phase_diff_deg:+.4f},"
                                                        f"{rx0_data['mag']:.2f},{rx1_data['mag']:.2f},"
                                                        f"{rx0_data['full_iq_str']},{rx1_data['full_iq_str']}\n")
                                    except Exception as csv_err:
                                        pass
                                        
                            # Display updated dashboard
                            ta_val = last_metrics[ue_id].get('ta', 0.0)
                            print_spatial_dashboard_mimo(ue_id, ta_val, last_metrics)
                            
                except Exception as e:
                    sys.stderr.write(f"Error parsing event: {e}\n")
                    sys.stderr.flush()
                    buffer = buffer[1:]

if __name__ == "__main__":
    try:
        run_xapp()
    except KeyboardInterrupt:
        print("\nDual-RX xApp Stopped.")
