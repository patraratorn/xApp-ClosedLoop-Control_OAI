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
        # T-Tracer 'buffer' fields contain a 4-byte length prefix.
        # We start parsing raw samples (c16_t: 16-bit real, 16-bit imag) directly.
        raw_data = np.frombuffer(srs_buffer, dtype=np.int16)
        
        # Guard check to avoid empty or corrupt data
        if len(raw_data) < 2:
            return 0.0, -140.0, 0, 0.0, "N/A", "N/A", False
            
        complex_data = raw_data[0::2] + 1j * raw_data[1::2]
        
        # Calculate average power & magnitude from raw I/Q samples
        avg_mag = np.mean(np.abs(complex_data))
        avg_power = np.mean(np.square(np.abs(complex_data)))
        
        # Define threshold to distinguish real SRS from physical USRP B210 noise floor
        # Background noise floor typically floats around 300-380 Magnitude on physical USRP
        srs_detected = avg_mag > 500.0
        
        # Extract first 3 samples for noise, or middle 3 samples for active signal (OFDM Guard Band bypass)
        if not srs_detected:
            first_3 = complex_data[:3]
            iq_str = ", ".join([f"{int(c.real):+d}{int(c.imag):+d}j" for c in first_3]) + " (Noise)"
            return 0.0, -120.0, 3, avg_mag, iq_str, "N/A", False
            
        # 1. RTT Calculation via IFFT (with FFT Shift & Negative Delay Handling)
        time_domain = np.fft.ifft(complex_data)
        N = len(time_domain)
        abs_td = np.abs(time_domain)
        peak_idx = np.argmax(abs_td)
        
        # Quadratic peak interpolation
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
        
        # If peak falls in the second half of the FFT window, it represents negative delay (aliased / phase shift)
        if refined_peak > N // 2:
            delay_samples = refined_peak - N
        else:
            delay_samples = refined_peak
            
        # Calibrate distance: negative delay is NOT clamped, natural phase lead/delay
        dist_m = ((delay_samples / SAMPLING_RATE) * SPEED_OF_LIGHT) / 2.0
            
        # 2. Calculate RSRP in dBm from physical I/Q samples (calibrated for USRP B210)
        norm_power = avg_power / (32768.0 ** 2)
        # Use realistic USRP calibration offset (-10.0 dBm) instead of simulator +30.0 dBm
        rsrp_dbm = 10.0 * np.log10(norm_power + 1e-12) - 10.0  
        rsrp_dbm = np.clip(rsrp_dbm, -140.0, -10.0)
        
        # 3. Estimate real physical SNR directly from active subcarriers (first-order difference noise estimation)
        # Filter active subcarriers (avoiding the zero-padded guard bands)
        active_samples = complex_data[np.abs(complex_data) > 10.0]
        if len(active_samples) > 5:
            # First-order difference to capture high-frequency noise floor in the active band
            diffs = np.diff(active_samples)
            noise_power = 0.5 * np.mean(np.square(np.abs(diffs)))
            total_power = np.mean(np.square(np.abs(active_samples)))
            signal_power = max(total_power - noise_power, 1e-10)
            snr_val = signal_power / (noise_power + 1e-10)
            # True unadulterated SNR
            snr_db = int(np.clip(10.0 * np.log10(snr_val), 1, 35))
        else:
            snr_db = 5
        
        
        # Bypass OFDM Guard Bands: Extract middle 3 subcarriers containing the actual SRS energy
        mid_idx = len(complex_data) // 2
        middle_3 = complex_data[mid_idx : mid_idx + 3]
        iq_str = ", ".join([f"{int(c.real):+d}{int(c.imag):+d}j" for c in middle_3])
        
        # Extract full complex samples for machine learning dataset (delimited by semicolon)
        full_iq_str = ";".join([f"{int(c.real):+d}{int(c.imag):+d}j" for c in complex_data])
        
        return dist_m, rsrp_dbm, snr_db, avg_mag, iq_str, full_iq_str, True
    except Exception as e:
        return 0.0, -140.0, 0, 0.0, "Error", "N/A", False

def print_spatial_dashboard(ue_id, dist_ta, dist_rtt, rsrp_dbm, snr_db, beam_id, avg_mag, iq_str, rsrp_kpm=None, srs_detected=False):
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
    print(" 📡      O-RAN REAL HARDWARE SRS PHYSICAL SPATIAL MONITOR      📡")
    print("=" * 68)
    print(f" 👤 UE RNTI:          0x{ue_id:04X} ({ue_id})")
    
    # SRS Signal Status
    if srs_detected:
        print(f" 📡 SRS Detection:    🟢 DETECTED (Active UL Transmission)")
    else:
        print(f" 📡 SRS Detection:    🟡 SEARCHING... (CPE Idle / Noise Floor)")
        
    # RTT Distance Display (No clamping, natural sign showing USRP Phase delays)
    if srs_detected:
        print(f" 🎯 RTT Distance:     {dist_rtt:+.2f} m (From raw SRS I/Q via IFFT)")
    else:
        print(f" 🎯 RTT Distance:     N/A (Awaiting CPE Active Traffic)")
        
    if dist_ta != 0.0:
        print(f" 📍 TA Distance:      {dist_ta:+.2f} m (From gNB MAC)")
    elif srs_detected:
        print(f" 📍 TA Distance:      {dist_rtt:+.2f} m (Estimated from SRS RTT)")
    else:
        print(f" 📍 TA Distance:      Calculating...")
        
    # Display RSRP: Prefer KPM measured RSRP if available, otherwise fallback to I/Q extracted SRS RSRP
    current_rsrp = rsrp_dbm
    if rsrp_kpm is not None and rsrp_kpm != 0.0:
        current_rsrp = rsrp_kpm
        print(f" 📶 Measured RSRP:    {rsrp_kpm:.1f} dBm (From gNB MAC Statistics)")
    else:
        print(f" 📶 Extracted RSRP:   {rsrp_dbm:.1f} dBm (From raw USRP B210 ADC)")
        
    if srs_detected:
        print(f" 🌟 Estimated SNR:    {snr_db} dB (Physical Noise Estimation)")
    else:
        print(f" 🌟 Estimated SNR:    N/A")
        
    print(f" ⚡ Avg IQ Magnitude: {avg_mag:.2f} (Physical USRP ADC level)")
    print(f" 🔮 First 3 IQ Raw:   [{iq_str}]")
    print("-" * 68)
    
    # Draw responsive ascii space map (safely clamp visualization index)
    map_length = 40
    # Map range up to 100m for simulation
    pos = max(0, min(int((dist_rtt / 100.0) * map_length), map_length - 1)) if srs_detected else -1
    
    sig_sym = "🟢" if current_rsrp >= -85 else "🟡" if current_rsrp >= -105 else "🔴"
    
    ascii_map = ["-"] * map_length
    if pos >= 0:
        ascii_map[pos] = sig_sym
        
    print("  [gNB] " + "".join(ascii_map) + (f" [UE] ({dist_rtt:+.2f} meters)" if srs_detected else " [UE] (Scanning...)"))
    print("=" * 68)
    print(" Tip: Run a data plane test (e.g. ping) from/to CPE to stimulate active telemetry.")
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
                            srs_det = last_metrics.get(ue_id, {}).get('detected', False)
                            # Protect SNR from being overwritten by 5 dB static value
                            physical_snr = last_metrics.get(ue_id, {}).get('physical_snr', snr)
                            print_spatial_dashboard(ue_id, dist_ta, rtt_val, 0.0, physical_snr, beam_id, avg_mag, iq_str, rsrp_kpm=rsrp, srs_detected=srs_det)
                            last_metrics[ue_id] = {'ta': dist_ta, 'rtt': rtt_val, 'mag': avg_mag, 'iq': iq_str, 'rsrp_kpm': rsrp, 'detected': srs_det, 'physical_snr': physical_snr}
                        
                    elif ev_id == ID_SRS:
                        # int,ue_id : int,ant_idx : int,port_idx : buffer,estimates
                        if len(payload) >= 12:
                            ue_id, ant, port = struct.unpack("iii", payload[:12])
                            
                            # Correction: Skip 4-byte buffer length prefix in T-Tracer binary protocol (payload[12:16]).
                            # Raw complex signal data starts precisely at offset 16 (payload[16:]).
                            srs_signal = payload[16:]
                            
                            rtt_dist, rsrp_dbm, snr_db, avg_mag, iq_str, full_iq_str, srs_det = estimate_rtt_and_extract_iq(srs_signal, ant, port, ue_id)
                            
                            # Keep track of metrics and preserve physical SNR
                            if ue_id not in last_metrics:
                                last_metrics[ue_id] = {'ta': 0.0, 'rtt': rtt_dist, 'mag': avg_mag, 'iq': iq_str, 'rsrp_kpm': None, 'detected': srs_det, 'physical_snr': snr_db}
                            else:
                                last_metrics[ue_id]['rtt'] = rtt_dist
                                last_metrics[ue_id]['mag'] = avg_mag
                                last_metrics[ue_id]['iq'] = iq_str
                                last_metrics[ue_id]['detected'] = srs_det
                                last_metrics[ue_id]['physical_snr'] = snr_db
                                
                            # CSV Logging logic when srs_det is True
                            if srs_det:
                                csv_file_path = "/home/beam/.gemini/tmp/demo/srs_dataset_real_hardware.csv"
                                try:
                                    os.makedirs(os.path.dirname(csv_file_path), exist_ok=True)
                                    file_exists = os.path.exists(csv_file_path)
                                    
                                    # We estimate TA from RTT or KPM
                                    ta_val = last_metrics[ue_id].get('ta', 0.0)
                                    if ta_val == 0.0:
                                        ta_val = rtt_dist # Estimate from RTT if MAC TA is not available
                                        
                                    current_rsrp = rsrp_dbm
                                    rsrp_kpm_val = last_metrics[ue_id].get('rsrp_kpm', None)
                                    if rsrp_kpm_val is not None and rsrp_kpm_val != 0.0:
                                        current_rsrp = rsrp_kpm_val
                                        
                                    with open(csv_file_path, "a") as csv_f:
                                        if not file_exists:
                                            csv_f.write("Timestamp,RNTI,RTT_Distance_m,TA_Distance_m,RSRP_dBm,SNR_dB,Avg_Magnitude,Raw_IQ_Middle_3,Raw_IQ_Full\n")
                                        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
                                        csv_f.write(f"{timestamp},0x{ue_id:04X},{rtt_dist:+.2f},{ta_val:+.2f},{current_rsrp:.1f},{snr_db},{avg_mag:.2f},{iq_str},{full_iq_str}\n")
                                except Exception as csv_err:
                                    pass # Prevent dashboard crash due to CSV write error
                                
                            # Display dashboard directly from SRS metrics!
                            ta_val = last_metrics[ue_id].get('ta', 0.0)
                            rsrp_kpm_val = last_metrics[ue_id].get('rsrp_kpm', None)
                            print_spatial_dashboard(ue_id, ta_val, rtt_dist, rsrp_dbm, snr_db, 0, avg_mag, iq_str, rsrp_kpm=rsrp_kpm_val, srs_detected=srs_det)
                                
                except Exception as e:
                    # Skip corrupt bytes
                    buffer = buffer[1:]

if __name__ == "__main__":
    try:
        run_xapp()
    except KeyboardInterrupt:
        print("\nxApp Stopped.")
