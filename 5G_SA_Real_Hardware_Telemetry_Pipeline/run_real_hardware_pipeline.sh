#!/bin/bash
# ====================================================================
# 📡 5G SA REAL HARDWARE MULTI-PROCESS ORCHESTRATION SCRIPT (TMUX)
# 👤 จัดทำโดย: นายภัทรธร สุภาพ (คุณ Beam)
# ====================================================================

# กำหนดค่าตัวแปรเส้นทางหลัก
RAW_OUT_DIR="/home/beam/.gemini/tmp/demo"
RAW_FILE="${RAW_OUT_DIR}/L1_metrics_RIS.raw"
GNB_CONF="/home/beam/openairinterface5g/targets/PROJECTS/GENERIC-NR-5GC/CONF/gnb.sa.band78.fr1.52PRB.usrpb210.custom.conf"

echo "===================================================================="
echo "📡  O-RAN REAL HARDWARE SYSTEM LAUNCHER (TMUX ORCHESTRATOR)      📡"
echo "===================================================================="

# 1. ตรวจสอบและเคลียร์โปรเซสและไฟล์ตกค้าง
echo "🧹 [1/4] ทำการล้างพอร์ตระบบและปิดโปรเซสตกค้าง..."
echo 'bbEEam167' | sudo -S pkill -f nearRT-RIC
echo 'bbEEam167' | sudo -S pkill -f nr-softmodem
echo 'bbEEam167' | sudo -S pkill -f parse_t_tracer_ris.py
echo 'bbEEam167' | sudo -S pkill -f record
rm -f "$RAW_FILE"
sleep 2

# 2. ตรวจสอบเครื่องมือ TMUX
if ! command -v tmux &> /dev/null; then
    echo "❌ [ERROR] ไม่พบเครื่องมือ tmux บนระบบกรุณาติดตั้งด้วยคำสั่ง: sudo apt install tmux"
    exit 1
fi

# 3. จัดเตรียม TMUX Session
SESSION_NAME="5g_oran_b210"
tmux kill-session -t "$SESSION_NAME" &> /dev/null

echo "🚀 [2/4] กำลังเริ่มต้นชุด TMUX Session: $SESSION_NAME..."
# สร้าง session และหน้าต่างแรกสำหรับ RIC
tmux new-session -d -s "$SESSION_NAME" -n "RIC"
tmux send-keys -t "${SESSION_NAME}:0" "/home/beam/flexric/build/examples/ric/nearRT-RIC" C-m

# รอ RIC สตาร์ทสแตนด์บายพอร์ต E2
sleep 2

# 4. สรรสร้างหน้าต่างและประชากรโปรเซส (RIC, T-Tracer, gNB, Dashboard)
echo "📡 [3/4] กำลังเชื่อมโยงท่อ Telemetry L1 PHY (T-Tracer)..."
# สร้างหน้าต่างสำหรับ T-Tracer
tmux new-window -t "$SESSION_NAME" -n "T-Tracer"
tmux send-keys -t "${SESSION_NAME}:1" "/home/beam/openairinterface5g/cmake_targets/ran_build/build/common/utils/T/tracer/record -d /home/beam/openairinterface5g/common/utils/T/T_messages.txt -o $RAW_FILE -on GNB_PHY_SRS_ESTIMATES_RIS -on GNB_PHY_L1_METRICS_RIS" C-m

sleep 2

echo "📶 [4/4] กำลังกระตุ้นสถานีฐาน gNB (USRP B210)..."
# สร้างหน้าต่างสำหรับ gNB
tmux new-window -t "$SESSION_NAME" -n "gNB-B210"
tmux send-keys -t "${SESSION_NAME}:2" "echo 'bbEEam167' | sudo -S stdbuf -oL -eL /home/beam/openairinterface5g/cmake_targets/ran_build/build/nr-softmodem -O $GNB_CONF -E --continuous-tx --T_stdout 0" C-m

# รอ gNB โหลด USRP firmware และทำ AMF Association สำเร็จ (ประมาณ 6 วินาที)
echo "⏳ กำลังรอสถานีฐานบูตระบบและเชื่อมต่อ Core Network..."
sleep 6

# สร้างหน้าต่างและแบ่งหน้าจอคู่สำหรับรัน Dashboard
echo "🖥️  ระบบบูตเสร็จสมบูรณ์! กำลังเปิดหน้าจอแดชบอร์ดประเมินตำแหน่ง RTT/SNR..."
tmux new-window -t "$SESSION_NAME" -n "Dashboard"
tmux send-keys -t "${SESSION_NAME}:3" "cd /home/beam/Desktop/ORAN-ClosedLoop-Control/5G_SA_Real_Hardware_Telemetry_Pipeline && python3 parse_t_tracer_ris.py" C-m

# เข้าสู่การแสดงผล TMUX ให้คุณ Beam สลับหน้าจอควบคุมได้อย่างอิสระ
tmux select-window -t "${SESSION_NAME}:3"
tmux attach-session -t "$SESSION_NAME"

echo "===================================================================="
echo "🟢 เชื่อมต่อระบบสำเร็จ! พิมพ์ 'tmux attach-session -t 5g_oran_b210' เพื่อดูล็อก"
echo "===================================================================="
