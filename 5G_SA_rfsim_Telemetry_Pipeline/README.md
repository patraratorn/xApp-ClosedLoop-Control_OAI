# คู่มือการติดตั้งและรันระบบจำลอง 5G SA Network ร่วมกับ Telemetry Pipeline แบบละเอียด

คู่มือฉบับนี้จัดทำขึ้นเพื่ออธิบายขั้นตอนปฏิบัติการรันและควบคุมระบบเครือข่ายจำลอง 5G Standalone (SA) ภายใต้สถาปัตยกรรม O-RAN ร่วมกับการสกัดข้อมูลสัญญาณดิบ **Sounding Reference Signal (SRS) I/Q sampling** ผ่าน **T-tracer** และการส่งสถิติประสิทธิภาพผ่าน **E2SM-KPM xApp** ออกสู่ช่องทาง **ZeroMQ** เพื่อวิเคราะห์ข้อมูลเชิงลึกในระดับเวลาจริง (Real-time)

---

## 🏗️ 1. โครงสร้างความเชื่อมโยงระบบ (System Topology)

ระบบจำลอง 5G SA Telemetry Pipeline ทำงานร่วมกันบนสภาวะแวดล้อมระบบเดี่ยว (Single Host Setup) ในโหมดช่องสัญญาณวิทยุจำลอง (`rfsimulator`) โดยมีความเชื่อมโยงการไหลของข้อมูลควบคุม (Control Plane) และข้อมูลผู้ใช้ (Data Plane/Telemetry) ดังแผนภาพ:

```mermaid
flowchart TD
    subgraph 5G Core Network (Docker Containers)
        AMF[oai-amf]
        UPF[oai-upf]
        MYSQL[(MySQL DB)]
        AUSF[oai-ausf]
        UDM[oai-udm]
        UDR[oai-udr]
        NRF[oai-nrf]
    end

    subgraph O-RAN Architecture
        RIC[Near-RT RIC / FlexRIC]
        xApp[KPM xApp / xapp_kpm_moni]
    end

    subgraph RAN Simulation (Host)
        gNB[gNB softmodem]
        UE[nrUE softmodem]
    end

    subgraph Telemetry & Dashboard
        Recorder[Telemetry Recorder / run_record.sh]
        ZMQ_Sub[ZMQ Subscriber / sub.py]
        Dashboard[Precision Spatial Dashboard]
    end

    %% Network Connections
    UE <-- rfsimulator / TCP 127.0.0.1 --> gNB
    gNB <-- NGAP/SCTP: Port 38412 --> AMF
    gNB <-- GTP-U/UDP: Port 2152 --> UPF
    gNB <-- E2AP/SCTP: Port 36421 --> RIC
    
    %% Telemetry Stream
    gNB -- T-tracer / TCP Port 2021 --> Recorder
    Recorder -- raw binary --> Dashboard
    
    RIC -- subscription --> xApp
    xApp -- ZMQ / TCP Port 5555 --> ZMQ_Sub
    ZMQ_Sub -- JSON Log --> ZMQ_Telemetry[(zmq_telemetry.json)]
```

### 📋 สรุปพอร์ตการเชื่อมโยงระบบที่สำคัญ
| อินเตอร์เฟส / ช่องทาง | โปรโตคอล | พอร์ตหลัก | หน้าที่การสื่อสาร |
| :--- | :--- | :--- | :--- |
| **N2 (gNB ↔ AMF)** | NGAP / SCTP | `38412` | ข้อมูลควบคุมระดับ Signaling และ NAS Procedure |
| **N3 (gNB ↔ UPF)** | GTP-U / UDP | `2152` | ข้อมูลทราฟฟิกของผู้ใช้ (Data Plane) |
| **E2 (gNB ↔ Near-RT RIC)** | E2AP / SCTP | `36421` | ข้อมูลรายงานและการส่งสัญญาณของ O-RAN |
| **T-Tracer (gNB ↔ Recorder)** | TCP socket | `2021` | สกัดข้อมูลบิตดิบ L1 PHY Metrics (SRS I/Q samples) |
| **ZeroMQ (xApp ↔ Subscriber)** | TCP stream | `5555` | สตรีมข้อมูล JSON สถิติประสิทธิภาพ Throughput และ PRB |
| **rfsimulator** | ideal TCP | `4043` | จำลองการรับส่งคลื่นสัญญาณวิทยุระหว่าง gNB และ UE |

---

## 🛠️ 2. ขั้นตอนการเตรียมการก่อนรัน (System Preparation)

ก่อนเริ่มต้นสั่งรัน เพื่อความเสถียรสูงสุดของระบบและป้องกันปัญหาพอร์ตชนกัน (Port Conflicts) หรือไฟล์ตกค้างเสียหาย ให้ดำเนินการล้างระบบและเตรียมการตามขั้นตอนต่อไปนี้:

### 2.1 ล้างโปรเซสและพอร์ตที่ตกค้างในระบบ
เปิดเทอร์มินัลและรันชุดคำสั่งเคลียร์หน่วยความจำ:
```bash
# ปิดกั้นการค้างคาของ Softmodem และแอปพลิเคชัน O-RAN
echo 'bbEEam167' | sudo -S pkill -9 nr-softmodem
echo 'bbEEam167' | sudo -S pkill -9 nr-uesoftmodem
pkill -9 nearRT-RIC
pkill -9 xapp_kpm_moni
pkill -9 python3
```

### 2.2 การเคลียร์ประวัติและไฟล์ Telemetry เก่า
การถอดรหัสบิตดิบผ่าน T-Tracer จำเป็นต้องเริ่มต้นที่หัวไฟล์เฟรม (Offset 0) เสมอ หากมีไฟล์เก่าค้างคาอยู่ ระบบประมวลผล IFFT อาจไม่สามารถจับจุดกึ่งกลางของคลื่นสัญญาณวิทยุได้:
```bash
rm -f /home/beam/.gemini/tmp/demo/L1_metrics_RIS.raw
rm -f /home/beam/.gemini/tmp/demo/zmq_telemetry.json
```

### 2.3 ตรวจสอบและตั้งค่าเน็ตเวิร์กบริดจ์สำหรับ OAI Core Network
ในการคุยกันระหว่าง gNB บนเครื่อง Host และ AMF ในคอนเทนเนอร์ Docker จะต้องใช้เน็ตเวิร์กบริดจ์ชื่อ `demo-oai` ซึ่งปกติแล้ว OAI Core Network จะตั้งค่า Gateway ไว้ที่ IP `192.168.70.129/26`:
```bash
# ตรวจสอบการเปิดใช้งานและ IP ของบริดจ์
ip addr show dev demo-oai
```
> [!IMPORTANT]
> หากอินเตอร์เฟส `demo-oai` ยังไม่มี IP Address หรือหลุดหายไป ให้ทำการผูก IP บริดจ์ใหม่ดังนี้:
> `echo 'bbEEam167' | sudo -S ip addr add 192.168.70.129/26 dev demo-oai`

---

## 🚀 3. ขั้นตอนการรันระบบตามลำดับ (Step-by-Step Execution Plan)

เพื่อให้โปรโตคอลการยืนยันตัวตนและการเข้าถึงเครือข่ายเชื่อมโยงกันอย่างราบรื่น **โปรดรันโปรเซสแยกหน้าจอเทอร์มินัลเรียงตามเฟสต่อไปนี้อย่างเคร่งครัด:**

### 🔹 Phase 1: การรัน 5G Core Network
สลับไปยังไดเรกทอรี docker-compose ของ Core Network และเริ่มการทำงาน:
```bash
cd /home/beam/oai-cn5g-fed/docker-compose
docker compose -f docker-compose-basic-nrf.yaml up -d
```
*   **การยืนยันผลสัมฤทธิ์:** ตรวจสอบสถานะการเชื่อมต่อของคอนเทนเนอร์ทั้งหมด 9 ตัว
    ```bash
    docker compose -f docker-compose-basic-nrf.yaml ps
    ```
    *ผลลัพธ์ที่คาดหวัง:* คอนเทนเนอร์ทุกตัว (mysql, oai-nrf, oai-amf, oai-smf, oai-upf, oai-udm, oai-udr, oai-ausf, oai-ext-dn) ต้องแสดงสถานะเป็น **healthy**

---

### 🔹 Phase 2: การเปิดใช้ Near-RT RIC (FlexRIC)
เปิดเทอร์มินัลใหม่ และสั่งรัน Near-RT RIC:
```bash
/home/beam/flexric/build/examples/ric/nearRT-RIC
```
*   **การยืนยันผลสัมฤทธิ์:** ปรากฏล็อกการทำงานแสดงว่าพร้อมรับการเชื่อมต่อ E2 Connection บนพอร์ต `36421`

---

### 🔹 Phase 3: การเริ่ม Telemetry Recorder (T-Tracer)
ก่อนที่คุณจะสั่งเริ่มสถานีฐาน gNB จำเป็นต้องเปิดตัวดักบิตข้อมูล L1 เพื่อรอการเชื่อมต่อจาก gNB เสมอ:
```bash
bash "/home/beam/Documents/Obsidian Vault/DEMO/run_record.sh"
```
*   **การยืนยันผลสัมฤทธิ์:** ปรากฏล็อกสถานะ `waiting for connection on 0.0.0.0:2021` ซึ่งเป็นการเปิด TCP socket รอกลุ่มตัวแปรสัญญาณ L1

---

### 🔹 Phase 4: การรันสถานีฐาน gNB (gNB softmodem)
เปิดเทอร์มินัลใหม่ และสั่งรัน gNB ในโหมด rfsimulator ภายใต้การควบคุมสัญญาณ T-Tracer:
```bash
echo 'bbEEam167' | sudo -S stdbuf -oL -eL /home/beam/openairinterface5g/cmake_targets/ran_build/build/nr-softmodem \
  -O /home/beam/oai-cn5g-fed/docker-compose/ran-conf/gnb.conf \
  --rfsim -E --continuous-tx --T_stdout 0 > /home/beam/.gemini/tmp/demo/gnb_softmodem.log 2>&1 &
```
*   **การยืนยันผลสัมฤทธิ์:** ติดตามและเฝ้าดูล็อกของ gNB
    ```bash
    tail -f /home/beam/.gemini/tmp/demo/gnb_softmodem.log
    ```
    *ล็อกสำคัญที่ต้องปรากฏ:*
    1.  **เชื่อมโยงกับ Core (AMF):** `[NGAP] Received NGAP_REGISTER_GNB_CNF: associated AMF 1`
    2.  **เชื่อมโยงกับ Near-RT RIC:** `[E2-AGENT]: E2 SETUP RESPONSE rx`
    3.  **เชื่อมโยงกับ T-Tracer:** `[T] connected to 127.0.0.1:2021`

---

### 🔹 Phase 5: การรันอุปกรณ์ปลายทาง nrUE (nrUE softmodem)
เมื่อสถานีฐานรันคงที่และสว่างในระบบแล้ว สั่งรันเครื่องจำลองอุปกรณ์ปลายทางเพื่อเริ่มกระบวนการสแกนและค้นหาโครงข่าย:
```bash
echo 'bbEEam167' | sudo -S stdbuf -oL -eL /home/beam/openairinterface5g/cmake_targets/ran_build/build/nr-uesoftmodem \
  -O /home/beam/oai-cn5g-fed/docker-compose/ran-conf/nr-ue.conf \
  --rfsim --rfsimulator.serveraddr 127.0.0.1 -C 3319680000 -r 106 --numerology 1 --band 78 --ssb 516 --thread-pool -1,-1 -E > /home/beam/.gemini/tmp/demo/nrue_softmodem.log 2>&1 &
```
*   **การยืนยันผลสัมฤทธิ์:** ติดตามและเฝ้าดูล็อกของ nrUE
    ```bash
    tail -f /home/beam/.gemini/tmp/demo/nrue_softmodem.log
    ```
    *ล็อกสำคัญที่ต้องปรากฏ:*
    1.  **Physical Layer Sync:** `pbch decoded successfully, PCI: 0` (เข้าสู่ In-Sync)
    2.  **RRC Setup:** `[NR_RRC] State = NR_RRC_CONNECTED` (เชื่อมต่อ RRC สมบูรณ์)
    3.  **PDU Session Setup:** `Interface oaitun_ue1 successfully configured, IPv4 12.1.1.66` (ได้รับ IP ของ Data Plane)

---

### 🔹 Phase 6: การเปิดใช้ KPM xApp และ ZeroMQ Telemetry Logger
เมื่ออุปกรณ์เชื่อมเครือข่ายเรียบร้อย ให้ดำเนินการรับส่งข้อมูล Telemetry:
1.  **รัน FlexRIC KPM xApp** เพื่อรับทราบ Performance Metrics:
    ```bash
    /home/beam/flexric/build/examples/xApp/c/monitor/xapp_kpm_moni &
    ```
2.  **เปิดตัวรับ Telemetry จากพอร์ต ZMQ** ไปบันทึกเก็บเป็นไฟล์ประวัติ:
    ```bash
    python3 -u /home/beam/.gemini/tmp/demo/sub.py &
    ```
*   **การยืนยันผลสัมฤทธิ์:** จะต้องมีโครงสร้างข้อมูล JSON บันทึกไหลลงมาในไฟล์ `/home/beam/.gemini/tmp/demo/zmq_telemetry.json` ทุกๆ 1.0 วินาทีอย่างสมเหตุสมผล

---

### 🔹 Phase 7: การเปิดใช้งาน Precision Spatial Dashboard
เปิดเทอร์มินัลใหม่ เพื่อรันหน้าจอแดชบอร์ดหลักสำหรับวิเคราะห์และตรวจจับคลื่นสัญญาณ SRS I/Q:
```bash
python3 /home/beam/.gemini/tmp/demo/parse_t_tracer_ris.py
```
*   **การแสดงผลที่ถูกต้อง:** หน้าจอแดชบอร์ด Terminal จะประมวลผลคำนวณ FFT/IFFT และวาดตำแหน่งพิกัด RNTI: `0x92CB` พร้อมแสดงค่า **SNR** (ปกติเฉลี่ยประมาณ `22 dB`) และ **RTT Distance** (`0.00 เมตร` บนช่องสัญญาณจำลองสมบูรณ์)

---

## 📈 4. วิธีทดสอบกระตุ้นระบบ Data Plane (iperf3 Activation)

ในสภาวะที่ไม่มีการแลกเปลี่ยนข้อมูลจริง สถิติ Throughput และการใช้ Resource Block (PRB) ในข้อความ Telemetry จะรายงานค่าเป็นศูนย์ เพื่อทดสอบการรับ-ส่งข้อมูลเต็มขีดความสามารถ ให้ทำตามขั้นตอนนี้:

### 4.1 ตรวจจับการสื่อสารผ่านคำสั่ง Ping กระตุ้นสัญญาณ
ใช้คำสั่ง Ping บังคับให้ออกทางอินเตอร์เฟสจำลอง 5GS เพื่อทดสอบเส้นทาง Routing:
```bash
ping -I oaitun_ue1 -c 10 192.168.70.135
```
*(เป้าหมาย: อัตราการสูญเสียแพ็กเกจเป็น 0% และค่า RTT สะท้อนเครือข่ายเสมือน)*

### 4.2 การรัน iperf3 ทดสอบ Throughput 10 วินาที
ยิงข้อมูล Data Traffic ระหว่าง UE (`12.1.1.66`) ไปยังปลายทาง Data Network (`192.168.70.135`):
```bash
iperf3 -c 192.168.70.135 -B 12.1.1.66 -t 10
```
*   **ค่าสถิติอ้างอิงความสำเร็จ:**
    *   **Throughput (DL/UL):** เฉลี่ยอยู่ในเกณฑ์ **55–60 Mbits/sec**
    *   **Packet Loss:** **0.0%**
    *   **PRB Usage:** Telemetry JSON บน ZeroMQ และแดชบอร์ดจะรายงานปริมาณการใช้งาน Resource Blocks ขยับสูงขึ้นตามทราฟฟิกข้อมูลจริง

---

## 🔍 5. วิธีแก้ไขสถานะและการดีบั๊กปัญหา (Troubleshooting)

เมื่อเกิดเหตุขัดข้องทางเทคนิคระหว่างทำการรันหรือทดสอบ ให้ปฏิบัติตามแนวทางการดีบั๊กมาตรฐานดังนี้:

### 5.1 การรีสตาร์ทระบบอย่างปลอดภัยแบบด่วน (Quick Restart)
หากสถานะเครือข่ายติดขัด ให้สับสคริปต์เพื่อล้างหน่วยความจำอย่างรวดเร็วก่อนรันรอบใหม่:
```bash
echo 'bbEEam167' | sudo -S pkill -9 nr-softmodem
echo 'bbEEam167' | sudo -S pkill -9 nr-uesoftmodem
pkill -9 nearRT-RIC
pkill -9 xapp_kpm_moni
```

### 5.2 วิธีแก้ปัญหา Dashboard ถอดรหัสบิตผิดพลาด (Frame Parse Error)
กรณีสัญญาณดิบในไฟล์ `.raw` เกิดอาการชำรุดจากการเชื่อมต่อและหลุดกระทันหัน (SCTP Shutdown loop) ให้ทำการสลัดไฟล์ดิบทิ้งก่อนการรัน gNB เสมอ:
```bash
rm -f /home/beam/.gemini/tmp/demo/L1_metrics_RIS.raw
```
*(เมื่อสั่งเริ่ม gNB softmodem ใหม่ ตัวบันทึกข้อมูลจะเริ่มเขียนบล็อกสัญญาณ L1 ถัดไปโดยเริ่มนับจาก Frame Boundary ที่ปลอดภัย)*

### 5.3 ตรวจสอบการเชื่อมต่อ Telemetry บน ZeroMQ ด้วยคำสั่งตรง
หากไม่มีสถิติไหลในไฟล์ JSON ให้ใช้ Python command สั้นๆ เพื่อดักจับดูว่า ZMQ Port 5555 กำลังปล่อยแพ็กเกจส่งออกมาหรือไม่:
```bash
python3 -c "import zmq; ctx = zmq.Context(); sock = ctx.socket(zmq.SUB); sock.connect('tcp://127.0.0.1:5555'); sock.setsockopt_string(zmq.SUBSCRIBE, ''); print(sock.recv_json())"
```
*(หากได้รับโครงสร้างข้อมูล `{ "DRB.UEThpDl": ... }` แสดงว่า O-RAN Telemetry Pipeline ฝั่ง xApp ทำงานได้อย่างมีประสิทธิภาพครบถ้วน)*

---
**เอกสารอ้างอิงโครงการ:** Obsidian Wiki `~/Documents/Obsidian Vault/DEMO/`
**รายงานผลสำเร็จโดย:** นายภัทรธร สุภาพ (คุณ Beam)
