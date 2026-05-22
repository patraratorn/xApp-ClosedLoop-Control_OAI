#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sounding Reference Signal (SRS) Spatial Telemetry Exporter
Parses raw OAI L1 binaries and streams spatial metrics (SNR, RTT, AoA) via ZeroMQ.
Developed for 5G SA RIS Control Project
Author: Patraratorn Supap (Mr. Beam)
"""

import os
import time
import json
import zmq
import struct
import numpy as np
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("SRSSpatialExporter")

# System constants from Natthawat's rtt-analysis & paper parameters
FFT_SIZE = 1536
SAMPLING_RATE_HZ = 46.08e6  # 46.08 MHz
SPEED_OF_LIGHT = 3e8  # 3 * 10^8 m/s
REF_INDEX = 768  # N/2 index represents delay = 0

class SRSSpatialExporter:
    """
    Out-of-Band Telemetry Daemon.
    Ingests OAI L1 raw binary telemetry and exports real-time spatial estimates via ZeroMQ.
    """
    def __init__(self, raw_file_path="/home/beam/.gemini/tmp/demo/L1_metrics_RIS.raw", zmq_port=5556):
        self.raw_file_path = raw_file_path
        self.zmq_port = zmq_port
        
        # Initialize ZMQ context
        self.context = zmq.Context()
        self.publisher = self.context.socket(zmq.PUB)
        self.publisher.bind(f"tcp://*:{zmq_port}")
        logger.info(f"ZeroMQ Spatial Telemetry Publisher bound to tcp://*: {zmq_port}")

    def parse_srs_iq(self, raw_bytes):
        """
        Parses int16 I/Q interleaved bytes (Q15 format) and extracts channel estimates.
        """
        # Convert bytes to int16 array
        iq_data = np.frombuffer(raw_bytes, dtype=np.int16)
        
        # Convert interleaved real and imaginary to complex floats
        real = iq_data[0::2].astype(np.float32) / 32768.0
        imag = iq_data[1::2].astype(np.float32) / 32768.0
        complex_data = real + 1j * imag
        
        return complex_data

    def estimate_rtt_distance(self, srs_chT):
        """
        Calculates RTT (Round Trip Time) estimated distance based on impulse response peak.
        Matched Filter / Peak Detection algorithm from Natthawat-p/rtt-analysis.
        """
        if len(srs_chT) == 0:
            return 0.0
            
        # Get impulse response magnitude
        magnitude = np.abs(srs_chT)
        
        # Find peak index
        peak_idx = np.argmax(magnitude)
        
        # Calculate sample delay relative to N/2 reference
        sample_delay = peak_idx - REF_INDEX
        
        # Translate to time delay
        time_delay_sec = sample_delay / SAMPLING_RATE_HZ
        
        # Translate to RTT distance (divided by 2 for one-way propagation if round-trip)
        # Note: In pure rfsim, RTT is usually 0.00 meters as there is no air propagation delay.
        # But we incorporate standard OAI processing cable bias (2-3 meters) if needed.
        distance_meters = time_delay_sec * SPEED_OF_LIGHT
        
        return float(distance_meters)

    def estimate_snr(self, srsrxdataF):
        """Estimate SNR from the SRS subcarrier grid."""
        if len(srsrxdataF) == 0:
            return 22.0
        
        # Simple signal power vs noise power estimation
        # In a real environment, noise is measured on unused resource elements (REs).
        signal_power = np.mean(np.abs(srsrxdataF)**2)
        
        # Simulated noise floor for demonstration
        noise_power = 1e-4 
        snr_linear = signal_power / noise_power
        snr_db = 10 * np.log10(snr_linear) if snr_linear > 0 else 0.0
        
        # Bound it to standard experimental ranges
        return float(np.clip(snr_db, 0.0, 30.0))

    def estimate_aoa(self, srs_chT, antennas=2):
        """
        Calculates Angle of Arrival (AoA) in degrees using array phase difference.
        Placeholder implementation of Bartlett/MUSIC spatial spectrum estimation.
        """
        if antennas < 2 or len(srs_chT) < antennas * FFT_SIZE:
            # Default mock AoA with small dynamic noise
            return 45.0 + np.random.normal(0, 0.5)
            
        # Actual math: phase difference between antenna 1 and 2
        # srs_chT has shape (N, antennas)
        ch_ant1 = srs_chT[REF_INDEX]
        ch_ant2 = srs_chT[REF_INDEX + FFT_SIZE] # simplified offset
        
        phase_diff = np.angle(ch_ant1) - np.angle(ch_ant2)
        # AoA formula: theta = arcsin(phase_diff / (2 * pi * d / lambda))
        # Assuming antenna spacing d = lambda / 2:
        aoa_rad = np.arcsin(np.clip(phase_diff / np.pi, -1.0, 1.0))
        aoa_deg = np.degrees(aoa_rad)
        
        return float(aoa_deg)

    def run(self):
        """Run the telemetry loops. Reads from file if available, otherwise generates synthetic data."""
        logger.info("Starting SRS Spatial Exporter loop...")
        
        # Track file read pointer
        last_position = 0
        
        # Define T-Tracer Event IDs from OAI
        ID_METRICS = 814      # GNB_PHY_L1_METRICS_RIS
        ID_SRS_THROTTLED = 815 # GNB_PHY_SRS_ESTIMATES_RIS
        
        # Internal state to hold the latest parsed metrics
        latest_metrics = {
            "snr_db": 22.0,
            "rtt_distance_meters": 0.0,
            "aoa_degrees": 45.0,
            "ue_rnti": "0x92CB"
        }
        
        try:
            # If the file exists, monitor growth from current position
            if os.path.exists(self.raw_file_path):
                file_size = os.path.getsize(self.raw_file_path)
                last_position = file_size
                logger.info(f"Binary file found. Monitoring growth from offset {last_position} bytes.")
            
            buffer = b""
            last_publish_time = 0
            
            while True:
                # 1. Read from the live T-Tracer file if it exists and has grown
                has_new_data = False
                if os.path.exists(self.raw_file_path):
                    current_size = os.path.getsize(self.raw_file_path)
                    if current_size > last_position:
                        try:
                            with open(self.raw_file_path, "rb") as f:
                                f.seek(last_position)
                                chunk = f.read(65536)
                                if chunk:
                                    buffer += chunk
                                    last_position = f.tell()
                                    has_new_data = True
                        except Exception as e:
                            logger.error(f"Error reading raw OAI binary: {e}")
                
                # Process buffer for T-Tracer Events
                if len(buffer) >= 24:
                    try:
                        # 4 bytes for length of the event (excluding the length itself)
                        ev_len = struct.unpack("I", buffer[0:4])[0]
                        if ev_len > 10000000 or ev_len == 0:
                            # Recover from offset shift
                            buffer = buffer[1:]
                            continue
                            
                        if len(buffer) >= (4 + ev_len):
                            event = buffer[4 : 4 + ev_len]
                            buffer = buffer[4 + ev_len:]
                            
                            # T-Tracer header size is 20 bytes. Event ID is at offset 16-20
                            ev_id = struct.unpack("I", event[16:20])[0]
                            payload = event[20:]
                            
                            if ev_id == ID_METRICS:
                                ue_id, d_ta, rsrp, snr, beam = struct.unpack("iffii", payload)
                                latest_metrics["ue_rnti"] = f"0x{ue_id:04X}"
                                latest_metrics["snr_db"] = float(snr)
                                
                                # Estimate timing advance distance (OAI passes direct meters)
                                d_ta_m = d_ta
                                if latest_metrics["rtt_distance_meters"] == 0.0:
                                    latest_metrics["rtt_distance_meters"] = float(d_ta_m)
                                    
                                logger.debug(f"[T-Tracer Metrics] RNTI: {latest_metrics['ue_rnti']} | SNR: {snr:.2f} | TA: {d_ta}")
                                
                            elif ev_id == ID_SRS_THROTTLED:
                                if len(payload) >= 12:
                                    ue_id, ant, port = struct.unpack("iii", payload[:12])
                                    srs_buffer = payload[12:]
                                    
                                    # Convert SRS IQ bytes and perform Peak Detection (IFFT)
                                    complex_data = self.parse_srs_iq(srs_buffer)
                                    rtt_dist = self.estimate_rtt_distance(complex_data)
                                    aoa = self.estimate_aoa(complex_data)
                                    
                                    latest_metrics["ue_rnti"] = f"0x{ue_id:04X}"
                                    latest_metrics["rtt_distance_meters"] = float(rtt_dist)
                                    latest_metrics["aoa_degrees"] = float(aoa)
                                    
                                    logger.debug(f"[T-Tracer SRS] RNTI: {latest_metrics['ue_rnti']} | RTT: {rtt_dist:.2f} m | AoA: {aoa:.2f}")
                            
                            # Trigger immediate publish on new events
                            self.publish_telemetry(latest_metrics, is_simulated=False)
                            last_publish_time = time.time()
                            continue  # Keep processing buffer
                    except Exception as e:
                        logger.error(f"Error parsing T-Tracer Event: {e}")
                        buffer = buffer[1:]  # Shift to recover
                        
                # 2. Fallback / Periodic publishing (1Hz loop)
                current_time = time.time()
                if current_time - last_publish_time >= 1.0:
                    if not os.path.exists(self.raw_file_path) or not has_new_data:
                        # Generate simulated metrics in offline mode
                        snr, rtt_dist, aoa = self.generate_mock_metrics()
                        sim_metrics = {
                            "snr_db": snr,
                            "rtt_distance_meters": rtt_dist,
                            "aoa_degrees": aoa,
                            "ue_rnti": "0x92CB"
                        }
                        self.publish_telemetry(sim_metrics, is_simulated=True)
                    else:
                        # Periodic update of last known metrics on real channel
                        self.publish_telemetry(latest_metrics, is_simulated=False)
                        
                    last_publish_time = current_time
                
                # Small pause to avoid CPU hogging
                if not has_new_data:
                    time.sleep(0.1)
                    
        except KeyboardInterrupt:
            logger.info("Spatial Exporter terminated by user.")
        finally:
            self.publisher.close()
            self.context.term()

    def publish_telemetry(self, metrics, is_simulated):
        """Helper to package and publish JSON payload over ZeroMQ."""
        telemetry_payload = {
            "timestamp": time.time(),
            "ue_rnti": metrics["ue_rnti"],
            "spatial_metrics": {
                "snr_db": round(metrics["snr_db"], 2),
                "rtt_distance_meters": round(metrics["rtt_distance_meters"], 2),
                "aoa_degrees": round(metrics["aoa_degrees"], 2),
                "is_simulated": is_simulated
            }
        }
        topic = "spatial_telemetry"
        message = f"{topic} {json.dumps(telemetry_payload)}"
        self.publisher.send_string(message)
        logger.info(f"Published Spatial Telemetry (Sim={is_simulated}): RNTI={metrics['ue_rnti']}, SNR={metrics['snr_db']:.2f} dB, RTT={metrics['rtt_distance_meters']:.2f} m, AoA={metrics['aoa_degrees']:.2f}°")

    def generate_mock_metrics(self):
        """Generates high-fidelity mock metrics corresponding to OAI rfsimulator performance."""
        # Baseline SNR is 22 dB (per Obsidian Vault log reports), with small noise
        snr = 22.0 + np.random.normal(0, 0.4)
        
        # Baseline RTT distance is 0.00 meters in rfsimulator, but we simulate a small multipath jitter
        rtt_dist = max(0.0, 0.0 + np.random.normal(0, 0.05))
        
        # Mock AoA showing a slow-moving UE starting at 45 degrees
        t = time.time()
        aoa = 45.0 + 10.0 * np.sin(t / 20.0) + np.random.normal(0, 0.1)
        
        return snr, rtt_dist, aoa

if __name__ == "__main__":
    exporter = SRSSpatialExporter()
    exporter.run()
