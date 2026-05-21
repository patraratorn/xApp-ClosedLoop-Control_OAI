# คู่มือปฏิบัติการรันระบบ 5G SA Network & O-RAN Telemetry แบบแมนนวล (Manual Command Book)

คู่มือฉบับนี้จัดทำขึ้นสำหรับวิศวกรผู้ดูแลโครงการเพื่อการรันระบบและติดตามโปรเซสการทำงานทีละคอมโพเนนต์ด้วยตนเอง (Manual Multi-Terminal Execution) เพื่อประโยชน์ในการตรวจสอบสถานะ ดีบั๊ก หรือเรียนรู้วิธีการทำงานเชิงลึกของโปรโตคอลในระบบจำลอง 5G SA Network ร่วมกับ Telemetry Pipeline

---

## 🛠️ 1. ขั้นตอนการเตรียมการใน Layer เน็ตเวิร์ก (Terminal 1)

ก่อนเริ่มรันบริการใดๆ ในระบบ ให้เตรียมสภาพแวดล้อมเน็ตเวิร์กและล้างหน่วยความจำเพื่อความพร้อม 100%

### 1.1 การปิดโปรเซสเก่าที่ตกค้างใน RAM
เปิด Terminal ที่ 1 และสั่งการเคลียร์โปรเซส:
```bash
# รหัสผ่าน sudo: bbEEam167
echo 'bbEEam167' | sudo -S pkill -9 nr-softmodem
echo 'bbEEam167' | sudo -S pkill -9 nr-uesoftmodem
pkill -9 nearRT-RIC
pkill -9 xapp_kpm_moni
pkill -9 -f sub.py
pkill -9 -f parse_t_tracer_ris.py
pkill -9 -f record
```

### 1.2 การจัดระเบียบเน็ตเวิร์กบริดจ์ของ OAI Core
ผูก IP Address เข้ากับเน็ตเวิร์กบริดจ์ `demo-oai` เพื่อให้เครื่อง Host สามารถสื่อสารกับ AMF ในด็อกเกอร์ผ่านอินเตอร์เฟส N2/N3 ได้:
```bash
echo 'bbEEam167' | sudo -S ip addr add 192.168.70.129/26 dev demo-oai
```
*(หากได้รับข้อความว่า File exists แสดงว่ามีการผูก IP ไว้เรียบร้อยแล้วและใช้งานได้ทันที)*

---

## 🚀 2. ขั้นตอนการเริ่มบริการตามลำดับหน้าจอ (Terminal 2 - Terminal 8)

เพื่อให้การแลกเปลี่ยนเครือข่ายเชื่อมโยงกันอย่างเสถียร **โปรดเปิดรันคำสั่งแยกตามเทอร์มินัลย่อยทีละเฟสตามลำดับดังต่อไปนี้:**

### 🖥️ Terminal 2: 5G Core Network
สลับไปยังโฟลเดอร์รัน Core Network และเปิดคอนเทนเนอร์ 9 ตัวหลัก:
```bash
cd /home/beam/oai-cn5g-fed/docker-compose
docker compose -f docker-compose-basic-nrf.yaml up -d
```
*   **คำสั่งเช็คสถานะความสำเร็จ:**
    ```bash
    docker compose -f docker-compose-basic-nrf.yaml ps
    ```
    *(รอประมาณ 15 วินาที ทุกคอนเทนเนอร์ต้องแสดงสถานะเป็น healthy)*

---

### 🖥️ Terminal 3: Near-RT RIC (FlexRIC)
เปิดใช้งานตัวจัดการ O-RAN Control Plane:
```bash
/home/beam/flexric/build/examples/ric/nearRT-RIC
```
*(ระบบจะสแตนด์บายเพื่อรอรับ E2 Connection จาก gNB softmodem ที่พอร์ต 36421)*

---

### 🖥️ Terminal 4: Telemetry Recorder (T-Tracer)
ล้างข้อมูลเก่าและเตรียมโปรเซส Recorder เพื่อดึงข้อมูลดิบ L1 PHY Metrics (SRS I/Q samples) รอดักฟังที่พอร์ต TCP 2021:
```bash
# ลบไฟล์สัญญาณดิบที่อาจชำรุดจากการทดลองรอบที่แล้ว
rm -f /home/beam/.gemini/tmp/demo/L1_metrics_RIS.raw

# รันตัวบันทึกข้อมูลดักพอร์ต
/home/beam/openairinterface5g/cmake_targets/ran_build/build/common/utils/T/tracer/record \
  -d /home/beam/openairinterface5g/common/utils/T/T_messages.txt \
  -o /home/beam/.gemini/tmp/demo/L1_metrics_RIS.raw \
  -on GNB_PHY_SRS_ESTIMATES_RIS \
  -on GNB_PHY_L1_METRICS_RIS
```

---

### 🖥️ Terminal 5: gNB softmodem (RAN Simulation)
รันสถานีฐานจำลองด้วยสิทธิ์ระดับสูงพร้อมส่งออก telemetry และบล็อกสัญญาณ:
```bash
echo 'bbEEam167' | sudo -S stdbuf -oL -eL /home/beam/openairinterface5g/cmake_targets/ran_build/build/nr-softmodem \
  -O /home/beam/oai-cn5g-fed/docker-compose/ran-conf/gnb.conf \
  --rfsim -E --continuous-tx --T_stdout 0
```
*   **ล็อกที่ต้องสังเกตเห็นยันยันความสำเร็จ:**
    1.  `associated AMF 1` (ต่อ Core สำเร็จ)
    2.  `E2 SETUP RESPONSE rx` (ต่อ Near-RT RIC สำเร็จ)
    3.  `connected to 127.0.0.1:2021` (ต่อ T-Tracer สำเร็จ)

---

### 🖥️ Terminal 6: nrUE softmodem (UE Simulation)
รันเครื่องมือจำลองอุปกรณ์ปลายทางเพื่อสแกนเครือข่ายและเชื่อมต่อ RRC:
```bash
echo 'bbEEam167' | sudo -S stdbuf -oL -eL /home/beam/openairinterface5g/cmake_targets/ran_build/build/nr-uesoftmodem \
  -O /home/beam/oai-cn5g-fed/docker-compose/ran-conf/nr-ue.conf \
  --rfsim --rfsimulator.serveraddr 127.0.0.1 -C 3319680000 -r 106 --numerology 1 --band 78 --ssb 516 --thread-pool -1,-1 -E
```
*   **ล็อกที่ต้องสังเกตเห็นยืนยันความสำเร็จ:**
    1.  `pbch decoded successfully, PCI: 0`
    2.  `State = NR_RRC_CONNECTED` (RRC Connection สำเร็จ)
    3.  `Interface oaitun_ue1 successfully configured, IPv4 12.1.1.66` (ได้รับ IP และ Data Plane สำเร็จ)

---

### 🖥️ Terminal 7: FlexRIC KPM xApp & ZeroMQ Subscriber
1.  **รัน KPM xApp** บนหน้าเทอร์มินัลหลัก เพื่อรับ Metrics จาก RIC:
    ```bash
    /home/beam/flexric/build/examples/xApp/c/monitor/xapp_kpm_moni
    ```
2.  **รัน ZMQ Subscriber** (เปิด Terminal ย่อยอีกอัน) เพื่อสตรีมสถิติดักแปลงเป็นโครงสร้าง JSON:
    ```bash
    python3 -u /home/beam/.gemini/tmp/demo/sub.py
    ```
    *(ตรวจสอบว่าไฟล์ `/home/beam/.gemini/tmp/demo/zmq_telemetry.json` มีข้อมูลขยับบันทึกใหม่ทุกๆ 1 วินาที)*

---

### 🖥️ Terminal 8: Precision Spatial Dashboard
เปิดระบบแสดงผลวิเคราะห์พิกัดคณิตศาสตร์และจุดศูนย์กลาง RNTI คลื่นสัญญาณ SRS I/Q:
```bash
python3 /home/beam/.gemini/tmp/demo/parse_t_tracer_ris.py
```
*(หน้าจอจะคำนวณ IFFT แสดงค่า SINR/SNR และระยะทาง RTT แบบเรียลไทม์ กด Ctrl+C เพื่อออก)*

---

## 📈 3. การรันทดสอบและดีบั๊กระบบเครือข่ายจำลอง

### 3.1 การกระตุ้นทราฟฟิกข้อมูลจริง (Terminal 9)
เปิด Terminal ใหม่เพื่อส่งทราฟฟิกข้อมูลจำลองให้ระบบสร้างรายงาน Performance Metrics:
```bash
# 1. ยิง ping กระตุ้นสัญญาณ
ping -I oaitun_ue1 -c 10 192.168.70.135

# 2. ทดสอบ Throughput สูงสุด 10 วินาที
iperf3 -c 192.168.70.135 -B 12.1.1.66 -t 10
```

### 3.2 ขั้นตอนการล้างระบบหลังเลิกใช้งาน (Cleanup CLI)
เพื่อคืนทรัพยากรให้ RAM และปิดระบบอย่างสมบูรณ์แบบปลอดภัย:
```bash
# 1. ล้างโปรเซส RAN/RIC
echo 'bbEEam167' | sudo -S pkill -9 nr-softmodem
echo 'bbEEam167' | sudo -S pkill -9 nr-uesoftmodem
pkill -9 nearRT-RIC
pkill -9 xapp_kpm_moni
pkill -9 python3

# 2. ปิด Core Network
cd /home/beam/oai-cn5g-fed/docker-compose
docker compose -f docker-compose-basic-nrf.yaml down
```

---
**เอกสารอ้างอิงโครงการ:** Obsidian Wiki `~/Documents/Obsidian Vault/DEMO/`  
**รายงานผลสำเร็จโดย:** นายภัทรธร สุภาพ (คุณ Beam)
