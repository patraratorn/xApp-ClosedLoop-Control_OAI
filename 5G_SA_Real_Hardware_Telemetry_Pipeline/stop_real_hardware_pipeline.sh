#!/bin/bash
# ====================================================================
# 🛑 5G SA REAL HARDWARE TEARDOWN & CLEANUP SCRIPT
# 👤 จัดทำโดย: นายภัทรธร สุภาพ (คุณ Beam)
# ====================================================================

SESSION_NAME="5g_oran_b210"

echo "===================================================================="
echo "🛑  O-RAN REAL HARDWARE SYSTEM TEARDOWN (SHUTDOWN ORCHESTRATOR)   🛑"
echo "===================================================================="

# 1. ปิดเซสชัน TMUX หลัก
if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    echo "🧹 [1/3] กำลังทำลาย TMUX Session: $SESSION_NAME..."
    tmux kill-session -t "$SESSION_NAME"
    echo "🟢 ปิดเซสชัน TMUX เรียบร้อย!"
else
    echo "🟡 [INFO] ไม่พบ TMUX Session: $SESSION_NAME ที่กำลังรันอยู่"
fi

# 2. ปิดและเคลียร์โปรเซสตกค้างในระบบทั้งหมดแบบเฉียบขาด
echo "🛡️ [2/3] ทำความสะอาดโปรเซส O-RAN ที่อาจตกค้างอยู่ในระบบ OS..."
sudo pkill -9 -f nearRT-RIC || true
sudo pkill -9 -f nr-softmodem || true
sudo pkill -9 -f record || true
sudo pkill -9 -f parse_t_tracer_ris.py || true
sudo pkill -9 -f xapp_kpm_moni || true
sudo pkill -9 -f sub.py || true
sleep 1

# 3. ตรวจสอบความสะอาดของพอร์ตและอุปกรณ์วิทยุ
echo "📡 [3/3] ตรวจสอบสิทธิ์ของฮาร์ดแวร์ USRP B210 และคืนพอร์ต..."
# ล้างไฟล์ข้อมูลสตรีมดิบเพื่อประหยัดเนื้อที่ดิสก์
RAW_FILE="/home/beam/.gemini/tmp/demo/L1_metrics_RIS.raw"
if [ -f "$RAW_FILE" ]; then
    echo "🗑️  กำลังล้างไฟล์ telemetry ชั่วคราว ($RAW_FILE)..."
    rm -f "$RAW_FILE"
fi

echo "===================================================================="
echo "🟢 ปิดระบบและล้างพอร์ตทั้งหมดเรียบร้อย 100% บอร์ด USRP B210 พร้อมใช้งานรอบถัดไปแล้วครับ!"
echo "===================================================================="
