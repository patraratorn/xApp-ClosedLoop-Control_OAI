#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sounding Reference Signal (SRS) Raw Binary Explorer & Mathematical Analyzer
Extracts real-time impulse responses, SNR, and RTT from OAI L1 output files.
Developed for 5G SA RIS Control Project
Author: Patraratorn Supap (Mr. Beam)
"""

import os
import sys
import numpy as np
import matplotlib.pyplot as plt
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("SRSExplorer")

# Parameters from Mundlamuri et al. (2024) paper & Natthawat's rtt-analysis
FFT_SIZE = 1024
SAMPLING_RATE = 30.72e6  # 30.72 MHz
SPEED_OF_LIGHT = 3e8  # 3 * 10^8 m/s
REF_INDEX = 512  # Center point N/2

def load_q15_binary(filepath):
    """
    Reads complex int16 values from the OAI raw binary log.
    Converts from Q15 interleaved format (int16 Real + int16 Imag) to complex floats.
    """
    if not os.path.exists(filepath):
        logger.error(f"Binary file not found: {filepath}")
        return None
        
    try:
        file_size = os.path.getsize(filepath)
        logger.info(f"Loading binary: {filepath} ({file_size / 1024 / 1024:.2f} MB)")
        
        # Each complex value consists of 2 bytes Real + 2 bytes Imag = 4 bytes
        # Read the file as an array of 16-bit integers
        raw_data = np.fromfile(filepath, dtype=np.int16)
        
        # Interleaved real and imaginary parts
        real = raw_data[0::2].astype(np.float32) / 32768.0
        imag = raw_data[1::2].astype(np.float32) / 32768.0
        complex_data = real + 1j * imag
        
        # Reshape to frames of FFT_SIZE
        num_samples = len(complex_data)
        num_frames = num_samples // FFT_SIZE
        
        if num_frames == 0:
            logger.error("File does not contain enough samples for at least 1 frame.")
            return None
            
        logger.info(f"Successfully loaded {num_frames} frames (each with {FFT_SIZE} complex samples)")
        
        # Truncate and reshape to (num_frames, FFT_SIZE)
        reshaped_data = complex_data[:num_frames * FFT_SIZE].reshape(num_frames, FFT_SIZE)
        return reshaped_data
    except Exception as e:
        logger.error(f"Error loading Q15 binary: {e}")
        return None

def analyze_frame_srs(srs_chT, frame_idx=0):
    """
    Performs Peak Detection to estimate time delay and RTT distance.
    Derived from Natthawat's implementation of Mundlamuri et al.'s equations.
    """
    # 1. Take magnitude of impulse response
    magnitude = np.abs(srs_chT)
    
    # 2. Identify Peak
    peak_idx = np.argmax(magnitude)
    peak_val = magnitude[peak_idx]
    
    # 3. Calculate delay in samples relative to reference index N/2
    sample_delay = peak_idx - REF_INDEX
    
    # 4. Convert to time delay
    time_delay = sample_delay / SAMPLING_RATE
    
    # 5. Convert to distance (RTT)
    distance = time_delay * SPEED_OF_LIGHT
    
    # 6. Estimate SNR (Signal-to-Noise Ratio)
    # Signal power is at the peak, noise floor estimated from outer regions
    signal_power = peak_val ** 2
    noise_region = np.concatenate([magnitude[:200], magnitude[-200:]])
    noise_power = np.mean(noise_region ** 2) if len(noise_region) > 0 else 1e-6
    
    snr_linear = signal_power / noise_power if noise_power > 0 else 1.0
    snr_db = 10 * np.log10(snr_linear)
    
    return {
        "frame": frame_idx,
        "peak_index": peak_idx,
        "sample_delay": sample_delay,
        "time_delay_ns": time_delay * 1e9,
        "estimated_distance_m": distance,
        "snr_db": snr_db
    }

def plot_channel_impulse_response(srs_chT, frame_idx=0, output_path="srs_impulse_response.png"):
    """
    Plots the Channel Impulse Response (CIR) and marks the estimated peak.
    """
    magnitude = np.abs(srs_chT)
    metrics = analyze_frame_srs(srs_chT, frame_idx)
    
    plt.figure(figsize=(10, 5), dpi=150)
    plt.plot(magnitude, label="Channel Impulse Response $|h(t)|$", color="#1f77b4", linewidth=1.5)
    plt.axvline(x=REF_INDEX, color="red", linestyle="--", label="Reference Zero-Delay ($N/2=768$)")
    plt.plot(metrics["peak_index"], magnitude[metrics["peak_index"]], "ro", label=f"Estimated Peak ({metrics['estimated_distance_m']:.2f} m)")
    
    plt.title(f"5G NR SRS Channel Impulse Response - Frame {frame_idx}\n"
              f"SNR: {metrics['snr_db']:.2f} dB | Est. Distance: {metrics['estimated_distance_m']:.2f} m", 
              fontsize=12, fontweight="bold", pad=15)
    plt.xlabel("Sample Index", fontsize=10)
    plt.ylabel("Magnitude", fontsize=10)
    plt.grid(True, linestyle=":", alpha=0.6)
    plt.legend(loc="upper right")
    
    # Premium visual adjustments
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()
    logger.info(f"Impulse response plot saved to: {output_path}")

if __name__ == "__main__":
    raw_file = "/home/beam/.gemini/tmp/demo/L1_metrics_RIS.raw"
    
    if len(sys.argv) > 1:
        raw_file = sys.argv[1]
        
    if not os.path.exists(raw_file):
        logger.warning(f"Default file {raw_file} not found. Running with high-fidelity simulated complex data...")
        # Generate simulated SRS channel impulse response with a peak at 10 meters (which is ~1.54 samples shift)
        # sample_shift = delay * fs = (10 / 3e8) * 46.08e6 = 1.536 samples
        synthetic_srs = np.random.normal(0, 0.05, (10, FFT_SIZE)).astype(np.complex64)
        for f in range(10):
            # Put peak at 768 + 2 (approx 13 meters)
            synthetic_srs[f, REF_INDEX + 2] = 1.0 + np.random.normal(0, 0.05)
            # Add exponential delay decay
            synthetic_srs[f, REF_INDEX + 3] = 0.5
            synthetic_srs[f, REF_INDEX + 4] = 0.2
            
        frames = synthetic_srs
    else:
        frames = load_q15_binary(raw_file)
        
    if frames is not None:
        # Analyze first frame
        metrics = analyze_frame_srs(frames[0], 0)
        print("\n==========================================")
        print("   SRS L1 PHYSICAL LAYER METRICS REPORT   ")
        print("==========================================")
        print(f"Target File:              {raw_file}")
        print(f"Total Frames Loaded:      {len(frames)}")
        print(f"SNR Estimate:             {metrics['snr_db']:.2f} dB")
        print(f"Peak Index:               {metrics['peak_index']} (Ref: {REF_INDEX})")
        print(f"Sample Delay:             {metrics['sample_delay']} samples")
        print(f"Time Delay:               {metrics['time_delay_ns']:.2f} ns")
        print(f"Estimated RTT Distance:   {metrics['estimated_distance_m']:.2f} meters")
        print("==========================================\n")
        
        # Save a plot of the first frame's impulse response
        plot_channel_impulse_response(frames[0], 0, "/home/beam/Python_ML/srs_impulse_response.png")
