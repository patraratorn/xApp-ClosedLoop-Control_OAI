#!/usr/bin/env python3
"""
realtime_aoa.py — Real-time AoA inference from T-tracer binary stream
======================================================================

ทำงาน:
  1. โหลด PhaseNet2 model ครั้งเดียวตอนเริ่ม (~1 MB, ใช้เวลา <0.5s)
  2. ติดตาม T-tracer binary file แบบ tail -f
  3. เมื่อได้ SRS packet ครบทั้ง RX0 + RX1 → infer AoA ทันที (<1 ms)
  4. แสดงผล + บันทึกลง CSV

Usage:
    python3 realtime_aoa.py
    python3 realtime_aoa.py --model /path/to/best_b210_phase.pt
    python3 realtime_aoa.py --raw /tmp/L1_metrics_RIS.raw --out aoa_log.csv
"""

import os, sys, struct, time, argparse
import numpy as np

# ── กำหนด path เริ่มต้น ────────────────────────────────────────────────────────
DEFAULT_RAW   = "/home/beam/.gemini/tmp/demo/L1_metrics_RIS.raw"
DEFAULT_MODEL = "/home/beam/Desktop/ORAN-ClosedLoop-Control/AoA/best_b210_phase.pt"
DEFAULT_OUT   = "/home/beam/Desktop/ORAN-ClosedLoop-Control/5G_SA_Real_Hardware_MIMO_2T2R_Pipeline/data/aoa_realtime_log.csv"

# ── Event IDs (T-tracer format) ────────────────────────────────────────────────
ID_METRICS = 0
ID_SRS     = 1

# ── Physical constants ─────────────────────────────────────────────────────────
_F_REAL   = 3.3197e9
_F_TRAIN  = 1.272e9
_C        = 299792458.0
_D_PHYS   = _C / (_F_TRAIN * 2)          # 0.1179 m
_D_LAMBDA = _D_PHYS / (_C / _F_REAL)     # 1.305 d/λ @ 3.3197 GHz
_PHASE_CORR = _F_TRAIN / _F_REAL         # 0.3832

# Hardware FFT layout (768-pt, DC at 384)
_LO = slice(96, 384)
_HI = slice(385, 673)


# ══════════════════════════════════════════════════════════════════════════════
# Signal Processing
# ══════════════════════════════════════════════════════════════════════════════

def extract_active_sc(arr: np.ndarray) -> np.ndarray:
    """เลือก active SC 576 ตัว (ข้าม guard bands + DC)"""
    if len(arr) < 673:
        return arr
    return np.concatenate([arr[_LO], arr[_HI]])  # (576,)


def extract_phase_features(rx0: np.ndarray, rx1: np.ndarray, n_sc=613) -> np.ndarray:
    """
    ① Extract 576 active SC
    ② Phase correction ×0.3832 (map 3.3197GHz → 1.272GHz)
    ③ Per-SC phase diff: angle(h1 × conj(h0))
    ④ Zero-pad → (613,) float32
    """
    h0 = extract_active_sc(rx0).astype(np.complex64)
    h1 = extract_active_sc(rx1).astype(np.complex64)
    n  = min(len(h0), len(h1), n_sc)

    def correct(h):
        return np.abs(h) * np.exp(1j * np.angle(h) * _PHASE_CORR)

    pd = np.angle(correct(h1[:n]) * np.conj(correct(h0[:n]))).astype(np.float32)
    if len(pd) < n_sc:
        pd = np.concatenate([pd, np.zeros(n_sc - len(pd), dtype=np.float32)])
    return pd[:n_sc]


def kay_aoa(rx0: np.ndarray, rx1: np.ndarray) -> float:
    """Kay estimator (fallback เมื่อไม่มี model)"""
    h0 = extract_active_sc(rx0)
    h1 = extract_active_sc(rx1)
    n  = min(len(h0), len(h1))
    phi = np.angle(np.sum(h1[:n] * np.conj(h0[:n])))
    return float(np.degrees(np.arcsin(np.clip(phi / (2 * np.pi * _D_LAMBDA), -1, 1))))


def parse_iq(raw_bytes: bytes) -> np.ndarray:
    """แปลง raw bytes (int16 IQ) → complex64 array"""
    raw = np.frombuffer(raw_bytes, dtype=np.int16)
    return (raw[0::2] + 1j * raw[1::2]).astype(np.complex64)


# ══════════════════════════════════════════════════════════════════════════════
# PhaseNet2 Model Loader
# ══════════════════════════════════════════════════════════════════════════════

class PhaseNet2Inferrer:
    """โหลดโมเดลและ infer AoA จาก phase feature vector"""

    def __init__(self, model_path: str):
        self.model  = None
        self.n_sc   = 613
        self.mae    = None
        self._load(model_path)

    def _load(self, path: str):
        if not os.path.exists(path):
            print(f"[PhaseNet2] ⚠  ไม่พบ model: {path}")
            print(f"[PhaseNet2]    → ใช้ Kay estimator แทน")
            return
        try:
            import torch
            import torch.nn as nn

            class _BBlock(nn.Module):
                """ตรงกับ weights จริงใน checkpoint (fc + relu ไม่มี Dropout)"""
                def __init__(self, i, o):
                    super().__init__()
                    self.fc = nn.Linear(i, o)
                def forward(self, x): return torch.relu(self.fc(x))

            class _Net(nn.Module):
                def __init__(self, n_sc=613):
                    super().__init__()
                    self.net = nn.ModuleList([
                        _BBlock(n_sc, 256), _BBlock(256, 256),
                        _BBlock(256, 128),  _BBlock(128, 64),
                        nn.Linear(64, 1)
                    ])
                def forward(self, x):
                    for l in self.net[:-1]: x = l(x)
                    return self.net[-1](x).squeeze(-1)

            ck = torch.load(path, map_location="cpu", weights_only=False)
            self.n_sc = ck.get("n_sc", 613)
            net = _Net(self.n_sc)
            net.load_state_dict(ck["state_dict"])
            net.eval()

            self._torch = torch
            self.model  = net
            self.mae    = ck.get("val_mae", None)
            ep          = ck.get("epoch", "?")
            ant_a       = ck.get("ant_a", 0)
            ant_b       = ck.get("ant_b", 13)
            mae_str     = f"{self.mae:.2f}°" if self.mae else "?"
            print(f"[PhaseNet2] ✅ โหลดสำเร็จ  epoch={ep}  val_mae={mae_str}  "
                  f"ant={ant_a}&{ant_b}  SC={self.n_sc}")
        except Exception as e:
            print(f"[PhaseNet2] ❌ โหลดล้มเหลว: {e}")

    def infer(self, rx0: np.ndarray, rx1: np.ndarray) -> tuple[float, str]:
        """คืนค่า (aoa_degrees, method_name)"""
        if len(rx0) == 0 or len(rx1) == 0:
            return 0.0, "N/A"

        if self.model is not None:
            try:
                feat = extract_phase_features(rx0, rx1, self.n_sc)
                x    = self._torch.from_numpy(feat).unsqueeze(0)
                with self._torch.no_grad():
                    aoa = float(self.model(x).item())
                if -90.0 <= aoa <= 90.0:
                    return aoa, "PhaseNet2"
            except Exception as e:
                print(f"[PhaseNet2] inference error: {e}", file=sys.stderr)

        return kay_aoa(rx0, rx1), "Kay"


# ══════════════════════════════════════════════════════════════════════════════
# CSV Logger
# ══════════════════════════════════════════════════════════════════════════════

class AoALogger:
    HEADER = "Timestamp,RNTI,AoA_deg,Method,Phase_Diff_deg,SNR_RX0,SNR_RX1\n"

    def __init__(self, path: str):
        self.path = path
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        is_new = not os.path.exists(path)
        self._f = open(path, "a", buffering=1)  # line-buffered
        if is_new:
            self._f.write(self.HEADER)
        print(f"[Logger]    📄 บันทึกลง: {path}")

    def log(self, rnti: int, aoa: float, method: str,
            phase_diff: float, snr0: int, snr1: int):
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        self._f.write(f"{ts},0x{rnti:04X},{aoa:+.3f},{method},"
                      f"{phase_diff:+.3f},{snr0},{snr1}\n")

    def close(self):
        self._f.close()


# ══════════════════════════════════════════════════════════════════════════════
# T-tracer Binary Parser
# ══════════════════════════════════════════════════════════════════════════════

def estimate_snr(arr: np.ndarray) -> int:
    active = arr[np.abs(arr) > 10.0]
    if len(active) < 5:
        return 0
    diffs = np.diff(active)
    noise = 0.5 * np.mean(np.abs(diffs) ** 2)
    sig   = max(np.mean(np.abs(active) ** 2) - noise, 1e-10)
    return int(np.clip(10 * np.log10(sig / (noise + 1e-10)), 0, 35))


def run(args):
    inferrer = PhaseNet2Inferrer(args.model)
    logger   = AoALogger(args.out)

    # สร้างไฟล์ถ้าไม่มี
    if not os.path.exists(args.raw):
        open(args.raw, "a").close()

    print(f"[Stream]    📡 กำลัง follow: {args.raw}")
    print(f"[Stream]    กด Ctrl+C เพื่อหยุด\n")
    WIN = getattr(args, 'avg', 20)  # moving average window
    print(f"[AoA]       averaging window = {WIN} slots\n")
    print(f"{'Time':>8}  {'RNTI':>6}  {'AoA (raw)':>10}  {'AoA (avg)':>10}  {'SNR0/1':>8}")
    print("-" * 55)

    buf          = b""
    ue_state: dict = {}   # rnti → {rx0, rx1, snr0, snr1, aoa_buf}
    count        = 0

    def open_raw(path, replay):
        f = open(path, "rb")
        if replay:
            f.seek(0)
            print("[Stream]    ⏪ REPLAY mode — อ่านข้อมูลจากต้นไฟล์")
        else:
            f.seek(0, 2)
        return f, os.stat(path).st_ino  # คืน file handle + inode

    f, cur_ino = open_raw(args.raw, getattr(args, 'replay', False))
    while True:
      try:
        chunk = f.read(65536)
        if not chunk:
            # ตรวจว่าไฟล์ถูกแทนที่ (rm + สร้างใหม่) หรือเปล่า
            try:
                new_ino = os.stat(args.raw).st_ino
                if new_ino != cur_ino:
                    print("\n[Stream]    🔄 ไฟล์ถูกสร้างใหม่ → เปิดใหม่...")
                    f.close()
                    f, cur_ino = open_raw(args.raw, False)
            except FileNotFoundError:
                pass
            time.sleep(0.02)
            continue

            buf += chunk

            while len(buf) >= 24:
                # ── parse event header ─────────────────────────────────────
                ev_len = struct.unpack("I", buf[:4])[0]
                if ev_len == 0 or ev_len > 3_000_000:
                    buf = buf[1:]
                    continue
                if len(buf) < 4 + ev_len:
                    break

                event  = buf[4 : 4 + ev_len]
                buf    = buf[4 + ev_len:]

                ev_id   = struct.unpack("I", event[16:20])[0]
                payload = event[20:]

                # ── SRS event ─────────────────────────────────────────────
                if ev_id == ID_SRS and len(payload) >= 12:
                    ue_id, ant, port = struct.unpack("iii", payload[:12])
                    raw_iq = payload[16:]

                    arr = parse_iq(raw_iq)
                    snr = estimate_snr(arr)
                    mag = float(np.mean(np.abs(arr)))

                    if ue_id not in ue_state:
                        ue_state[ue_id] = {"rx0": np.array([]), "rx1": np.array([]),
                                           "snr0": 0, "snr1": 0, "aoa_buf": []}

                    if ant == 0:
                        ue_state[ue_id]["rx0"]  = arr
                        ue_state[ue_id]["snr0"] = snr
                    else:
                        ue_state[ue_id]["rx1"]  = arr
                        ue_state[ue_id]["snr1"] = snr

                    st = ue_state[ue_id]
                    rx0, rx1 = st["rx0"], st["rx1"]

                    # ── เมื่อมีทั้งสองเสา → infer ทันที ──────────────────
                    if (len(rx0) > 0 and len(rx1) > 0
                            and mag > 400.0):       # SRS detected threshold

                        aoa, method = inferrer.infer(rx0, rx1)

                        # Moving average — buffer ขนาด WIN slots
                        buf_aoa = st["aoa_buf"]
                        buf_aoa.append(aoa)
                        if len(buf_aoa) > WIN:
                            buf_aoa.pop(0)
                        aoa_avg = float(np.mean(buf_aoa))

                        # Phase diff สำหรับ log เท่านั้น (ไม่แสดง)
                        n = min(len(rx0), len(rx1))
                        phase_diff = float(np.degrees(
                            np.angle(np.sum(rx0[:n] * np.conj(rx1[:n])))
                        ))
                        logger.log(ue_id, aoa_avg, method, phase_diff,
                                   st["snr0"], st["snr1"])

                        count += 1
                        ts = time.strftime("%H:%M:%S")
                        bar_pos = int(((aoa_avg + 25) / 50) * 20)
                        bar_pos = max(0, min(19, bar_pos))
                        bar = ["-"] * 20
                        bar[10] = "|"
                        bar[bar_pos] = "●"
                        print(f"{ts}  {ue_id:#06x}  {aoa:>+9.2f}°  "
                              f"{aoa_avg:>+9.2f}°  "
                              f"{st['snr0']:2d}/{st['snr1']:2d} dB  "
                              f"[-25°{''.join(bar)}+25°]")
                        sys.stdout.flush()

      except Exception as e:
        sys.stderr.write(f"parse error: {e}\n")
        buf = buf[1:] if buf else buf


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw",    default=DEFAULT_RAW,   help="T-tracer binary file")
    ap.add_argument("--model",  default=DEFAULT_MODEL, help="best_b210_phase.pt path")
    ap.add_argument("--out",    default=DEFAULT_OUT,   help="CSV output path")
    ap.add_argument("--replay", action="store_true",   help="อ่านข้อมูลเก่าจากต้นไฟล์ (สำหรับทดสอบ)")
    ap.add_argument("--avg",    type=int, default=20,  help="moving average window (default=20 slots)")
    args = ap.parse_args()

    try:
        run(args)
    except KeyboardInterrupt:
        print("\n[Stopped]")
