#!/bin/bash

# ==============================================================================
# 📡 5G SA Network & O-RAN Telemetry System - Master Controller
# ==============================================================================
# พัฒนาขึ้นสำหรับคุณ Beam (นายภัทรธร สุภาพ) เพื่ออำนวยความสะดวกในการรันระบบครบวงจร
# รันผ่านเทอร์มินัลเดียวอย่างปลอดภัย มีการจัดการโปรเซสใน background และ logs ชัดเจน
# รหัสผ่าน sudo ในตัวเครื่อง: bbEEam167
# ==============================================================================

# สีสำหรับแสดงผลสวยงาม (ANSI Colors)
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

SUDO_PASS="bbEEam167"
LOG_DIR="/home/beam/.gemini/tmp/demo"
mkdir -p "$LOG_DIR"

show_header() {
    clear
    echo -e "${CYAN}======================================================================${NC}"
    echo -e "${BOLD}${BLUE}   📡 5G SA & O-RAN TELEMETRY PIPELINE MASTER CONTROLLER (STABLE)     ${NC}"
    echo -e "${CYAN}======================================================================${NC}"
    echo -e "   [สถานะปัจจุบันและคำสั่งจัดการด่วนสำหรับคุณ Beam]"
    echo -e "   Logs Directory: ${YELLOW}$LOG_DIR${NC}"
    echo -e "${CYAN}----------------------------------------------------------------------${NC}"
}

check_process() {
    local proc_name=$1
    if pgrep -f "$proc_name" > /dev/null; then
        echo -e "${GREEN}● RUNNING${NC}"
    else
        echo -e "${RED}○ STOPPED${NC}"
    fi
}

check_docker_container() {
    local container_name=$1
    if [ "$(docker inspect -f '{{.State.Running}}' "$container_name" 2>/dev/null)" == "true" ]; then
        echo -e "${GREEN}● RUNNING (Healthy)${NC}"
    else
        echo -e "${RED}○ STOPPED${NC}"
    fi
}

show_status() {
    echo -e "${BOLD}[สถานะบริการในระบบ (System Status)]${NC}"
    echo -n "  1. 5G Core AMF (Docker):     "
    check_docker_container "oai-amf"
    echo -n "  2. Near-RT RIC (FlexRIC):    "
    check_process "nearRT-RIC"
    echo -n "  3. Telemetry Recorder (L1):  "
    check_process "record -d"
    echo -n "  4. gNB softmodem (RAN):      "
    check_process "nr-softmodem"
    echo -n "  5. nrUE softmodem (UE):      "
    check_process "nr-uesoftmodem"
    echo -n "  6. KPM xApp (FlexRIC):       "
    check_process "xapp_kpm_moni"
    echo -n "  7. ZMQ Subscriber (Logger):  "
    check_process "sub.py"
    echo -n "  8. Precision Dashboard:      "
    check_process "parse_t_tracer_ris.py"
    echo -e "${CYAN}----------------------------------------------------------------------${NC}"
}

clean_system() {
    echo -e "${YELLOW}🧹 กำลังล้างโปรเซสเก่าและสิทธิ์ที่ตกค้างในระบบ...${NC}"
    echo "$SUDO_PASS" | sudo -S pkill -9 nr-softmodem 2>/dev/null
    echo "$SUDO_PASS" | sudo -S pkill -9 nr-uesoftmodem 2>/dev/null
    pkill -9 nearRT-RIC 2>/dev/null
    pkill -9 xapp_kpm_moni 2>/dev/null
    pkill -9 -f sub.py 2>/dev/null
    pkill -9 -f parse_t_tracer_ris.py 2>/dev/null
    pkill -9 -f record 2>/dev/null
    echo -e "${GREEN}✔ ล้างข้อมูลและโปรเซส RAN / RIC เรียบร้อยแล้ว!${NC}"
    sleep 1.5
}

setup_network() {
    echo -e "${YELLOW}🌐 กำลังตรวจสอบและตั้งค่า Network Bridge 'demo-oai'...${NC}"
    if ! ip addr show dev demo-oai &>/dev/null; then
        echo -e "${RED}✗ ไม่พบอินเตอร์เฟส demo-oai! กรุณารัน Phase 1 (5G Core) ก่อน${NC}"
    else
        # เช็คว่ามี IP 192.168.70.129 ผูกอยู่หรือไม่
        if ip addr show dev demo-oai | grep -q "192.168.70.129"; then
            echo -e "${GREEN}✔ Network Bridge ได้รับการกำหนด IP 192.168.70.129 แล้ว${NC}"
        else
            echo -e "${YELLOW}🛠️ กำลังผูก IP 192.168.70.129 เข้ากับอินเตอร์เฟส...${NC}"
            echo "$SUDO_PASS" | sudo -S ip addr add 192.168.70.129/26 dev demo-oai 2>/dev/null
            echo -e "${GREEN}✔ ผูก IP เรียบร้อยแล้ว${NC}"
        fi
    fi
    sleep 1.5
}

start_core() {
    echo -e "${YELLOW}🚀 กำลังเริ่มรัน 5G Core Network (OAI CN)...${NC}"
    cd /home/beam/oai-cn5g-fed/docker-compose
    docker compose -f docker-compose-basic-nrf.yaml up -d
    echo -e "${GREEN}✔ ส่งคำสั่ง docker-compose up เรียบร้อยแล้ว!${NC}"
    echo -e "${YELLOW}⏳ รอระบบเปิดตัว 15 วินาที...${NC}"
    sleep 15
}

stop_core() {
    echo -e "${YELLOW}🛑 กำลังปิด 5G Core Network...${NC}"
    cd /home/beam/oai-cn5g-fed/docker-compose
    docker compose -f docker-compose-basic-nrf.yaml down
    echo -e "${GREEN}✔ ปิดระบบ Core Network เรียบร้อย${NC}"
    sleep 2
}

start_ric() {
    if pgrep -f "nearRT-RIC" > /dev/null; then
        echo -e "${YELLOW}⚠ RIC กำลังทำงานอยู่แล้ว!${NC}"
    else
        echo -e "${YELLOW}🚀 กำลังเริ่ม Near-RT RIC (FlexRIC) ใน background...${NC}"
        /home/beam/flexric/build/examples/ric/nearRT-RIC > "$LOG_DIR/nearRT_ric.log" 2>&1 &
        echo -e "${GREEN}✔ เริ่ม RIC เรียบร้อยแล้ว! (Log: nearRT_ric.log)${NC}"
    fi
    sleep 1.5
}

start_recorder() {
    if pgrep -f "record -d" > /dev/null; then
        echo -e "${YELLOW}⚠ Telemetry Recorder ทำงานอยู่แล้ว!${NC}"
    else
        echo -e "${YELLOW}🚀 กำลังล้างไฟล์ดิบเก่าและรัน T-Tracer Recorder...${NC}"
        rm -f "$LOG_DIR/L1_metrics_RIS.raw"
        bash "/home/beam/Documents/Obsidian Vault/DEMO/run_record.sh" > "$LOG_DIR/recorder.log" 2>&1 &
        echo -e "${GREEN}✔ เริ่ม Telemetry Recorder เรียบร้อย! รอดักจับสัญญาณที่พอร์ต 2021${NC}"
    fi
    sleep 1.5
}

start_gnb() {
    if pgrep -f "nr-softmodem" > /dev/null; then
        echo -e "${YELLOW}⚠ gNB softmodem กำลังทำงานอยู่แล้ว!${NC}"
    else
        echo -e "${YELLOW}📡 กำลังเริ่มรัน gNB Softmodem (Simulation + T-Tracer)...${NC}"
        echo "$SUDO_PASS" | sudo -S stdbuf -oL -eL /home/beam/openairinterface5g/cmake_targets/ran_build/build/nr-softmodem \
          -O /home/beam/oai-cn5g-fed/docker-compose/ran-conf/gnb.conf \
          --rfsim -E --continuous-tx --T_stdout 0 > "$LOG_DIR/gnb_softmodem.log" 2>&1 &
        echo -e "${GREEN}✔ ส่งคำสั่งเริ่ม gNB สำเร็จ! (Log: gnb_softmodem.log)${NC}"
        echo -e "${YELLOW}⏳ รอเชื่อมโยง AMF และ RIC 10 วินาที...${NC}"
        sleep 10
    fi
}

start_ue() {
    if pgrep -f "nr-uesoftmodem" > /dev/null; then
        echo -e "${YELLOW}⚠ nrUE softmodem กำลังทำงานอยู่แล้ว!${NC}"
    else
        echo -e "${YELLOW}📱 กำลังเริ่มรัน nrUE softmodem (Simulation)...${NC}"
        echo "$SUDO_PASS" | sudo -S stdbuf -oL -eL /home/beam/openairinterface5g/cmake_targets/ran_build/build/nr-uesoftmodem \
          -O /home/beam/oai-cn5g-fed/docker-compose/ran-conf/nr-ue.conf \
          --rfsim --rfsimulator.serveraddr 127.0.0.1 -C 3319680000 -r 106 --numerology 1 --band 78 --ssb 516 --thread-pool -1,-1 -E > "$LOG_DIR/nrue_softmodem.log" 2>&1 &
        echo -e "${GREEN}✔ ส่งคำสั่งเริ่ม nrUE สำเร็จ! (Log: nrue_softmodem.log)${NC}"
        echo -e "${YELLOW}⏳ รอการสแกนและยืนยัน IP Address 15 วินาที...${NC}"
        sleep 15
    fi
}

start_xapp() {
    if pgrep -f "xapp_kpm_moni" > /dev/null; then
        echo -e "${YELLOW}⚠ KPM xApp ทำงานอยู่แล้ว!${NC}"
    else
        echo -e "${YELLOW}📊 กำลังรัน KPM xApp และ ZeroMQ Subscriber...${NC}"
        /home/beam/flexric/build/examples/xApp/c/monitor/xapp_kpm_moni > "$LOG_DIR/kpm_xapp.log" 2>&1 &
        sleep 2
        python3 -u /home/beam/.gemini/tmp/demo/sub.py > "$LOG_DIR/zmq_sub.log" 2>&1 &
        echo -e "${GREEN}✔ เริ่มรัน xApp และ Logger (ZMQ Port 5555) เรียบร้อย!${NC}"
    fi
    sleep 1.5
}

start_dashboard() {
    echo -e "${YELLOW}🖥️ กำลังเริ่มรัน Precision Spatial Dashboard ใน foreground...${NC}"
    echo -e "${BLUE}>>> กด Ctrl+C เพื่อออกจากแดชบอร์ดและกลับสู่เมนูหลัก${NC}"
    sleep 2
    python3 /home/beam/.gemini/tmp/demo/parse_t_tracer_ris.py
}

run_data_plane_test() {
    echo -e "${YELLOW}📊 [เริ่มการทดสอบ Data Plane กระตุ้นระบบ Telemetry]${NC}"
    echo -e "--------------------------------------------------------"
    echo -e "${CYAN}1. กำลังส่งคำสั่ง PING เพื่อกระตุ้น RRC/GTP-U Tunnel...${NC}"
    ping -I oaitun_ue1 -c 5 192.168.70.135
    
    echo -e "\n${CYAN}2. กำลังยิง iperf3 Throughput Test ไปยัง Core DN (10 วินาที)...${NC}"
    iperf3 -c 192.168.70.135 -B 12.1.1.66 -t 10
    
    echo -e "--------------------------------------------------------"
    echo -e "${GREEN}✔ ทดสอบกระตุ้นสัญญาณเสร็จสมบูรณ์! คุณสามารถเปิดตรวจสอบหน้าจอแดชบอร์ดได้แล้ว${NC}"
    echo -e "กด Enter เพื่อกลับไปเมนูหลัก..."
    read -r
}

tail_logs() {
    echo -e "${BOLD}[เลือกไฟล์ Log ที่ต้องการติดตาม (Tail Log)]${NC}"
    echo "  1) gNB Softmodem Log"
    echo "  2) nrUE Softmodem Log"
    echo "  3) Near-RT RIC Log"
    echo "  4) KPM xApp Log"
    echo "  5) Telemetry ZMQ JSON Log"
    echo "  0) Back to Main Menu"
    echo -n "กรุณาระบุทางเลือก [0-5]: "
    read -r log_choice
    case $log_choice in
        1) tail -n 50 -f "$LOG_DIR/gnb_softmodem.log" ;;
        2) tail -n 50 -f "$LOG_DIR/nrue_softmodem.log" ;;
        3) tail -n 50 -f "$LOG_DIR/nearRT_ric.log" ;;
        4) tail -n 50 -f "$LOG_DIR/kpm_xapp.log" ;;
        5) tail -n 50 -f "$LOG_DIR/zmq_telemetry.json" ;;
        *) return ;;
    esac
}

# ลูปเมนูหลักอินเตอร์แอคทีฟ
while true; do
    show_header
    show_status
    echo -e "${BOLD}[เลือกขั้นตอนที่ต้องการดำเนินการ (Operations Menu)]${NC}"
    echo -e "  ${BLUE}1)${NC} ${BOLD}[PREPARE]${NC} เคลียร์ระบบ RAN/RIC และเปิด Gateway Bridge"
    echo -e "  ${BLUE}2)${NC} ${BLUE}[PHASE 1]${NC} รัน 5G Core Network"
    echo -e "  ${BLUE}3)${NC} ${BLUE}[PHASE 2]${NC} รัน Near-RT RIC (FlexRIC)"
    echo -e "  ${BLUE}4)${NC} ${BLUE}[PHASE 3]${NC} เปิด Telemetry Recorder (T-Tracer)"
    echo -e "  ${BLUE}5)${NC} ${BLUE}[PHASE 4]${NC} รัน gNB Softmodem (Simulation)"
    echo -e "  ${BLUE}6)${NC} ${BLUE}[PHASE 5]${NC} รัน nrUE Softmodem (Simulation)"
    echo -e "  ${BLUE}7)${NC} ${BLUE}[PHASE 6]${NC} เปิดใช้งาน xApp & ตัวสตรีม ZeroMQ"
    echo -e "  ${BLUE}8)${NC} ${BLUE}[PHASE 7]${NC} เปิดใช้งาน Precision Spatial Dashboard"
    echo -e "  ${BLUE}9)${NC} ${YELLOW}[TEST]${NC}    ทดสอบยิง iperf3 Data Plane"
    echo -e "  ${BLUE}10)${NC} ${YELLOW}[TAIL]${NC}   เฝ้าติดตามดูไฟล์ Logs ต่างๆ"
    echo -e "  ${BLUE}99)${NC} ${RED}[RESET]${NC}   ปิดและล้างทุกบริการจำลองในระบบ (RAN/RIC/Core)"
    echo -e "  ${BLUE}0)${NC} Exit"
    echo -e "${CYAN}======================================================================${NC}"
    echo -n "ระบุหมายเลขการทำงาน [0-99]: "
    read -r choice

    case $choice in
        1) clean_system; setup_network ;;
        2) start_core ;;
        3) start_ric ;;
        4) start_recorder ;;
        5) start_gnb ;;
        6) start_ue ;;
        7) start_xapp ;;
        8) start_dashboard ;;
        9) run_data_plane_test ;;
        10) tail_logs ;;
        99) clean_system; stop_core ;;
        0) echo -e "\n${GREEN}👋 ขอบคุณครับคุณ Beam! ขอให้การทดลองดำเนินไปได้ด้วยดีครับ${NC}"; exit 0 ;;
        *) echo -e "${RED}✗ ตัวเลือกไม่ถูกต้อง!${NC}"; sleep 1 ;;
    esac
done
