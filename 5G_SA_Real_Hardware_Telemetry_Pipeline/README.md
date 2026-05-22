# 📡 5G SA Real Hardware Telemetry & Deep Learning Dataset Pipeline
## คู่มือปฏิบัติการและระบบวิเคราะห์สกัดฟิสิกส์วิทยุคลื่น SRS ดิบบน USRP B210 และ 5G CPE

---

## 🌟 1. ภาพรวมสถาปัตยกรรมระดับฮาร์ดแวร์ (Hardware Architecture Overview)

ระบบวิทยุ 5G Standalone (5G SA) ของเราเป็นระบบฮาร์ดแวร์จริงระดับอ้างอิงเชิงพาณิชย์และมาตรฐาน O-RAN ซึ่งประกอบด้วยฮาร์ดแวร์หลักดังนี้:

1. **สถานีฐาน (OAI gNB + USRP B210):**
   * **SDR Platform:** Ettus Research USRP B210 เชื่อมต่อผ่านบัส USB 3.0 สำหรับรับส่งสัญญาณ RF ในย่าน Band 78 (TDD 3.5 GHz)
   * **Clock Synchronization:** ระบบติดตั้งและควบคุมผ่านสัญญาณนาฬิกาอ้างอิงภายนอก (10 MHz External Reference Clock) เพื่อป้องกันปัญหาความถี่เลื่อนไหล (Frequency Drift) และ Sampling Slip
   * **Processing Platform:** ทำงานบนระบบปฏิบัติการ Ubuntu Real-Time Kernel (Low-Latency) ควบคุมการจัดตารางเวลาคลื่นวิทยุระดับ L1/L2 ผ่าน OAI gNB Softmodem และโมดูล E2 Agent
2. **อุปกรณ์ผู้ใช้งานปลายทาง (5G CPE Module):**
   * โมดูลรับส่งสัญญาณวิทยุ 5G เชิงพาณิชย์สำหรับการกระตุ้นช่องสัญญาณอัปลิงก์
   * ทำการส่งคลื่นสัญญาณอ้างอิง **Sounding Reference Signal (SRS)** ในระดับ PHY Layer เมื่อมีการสตรีมหรือส่งถ่ายทราฟฟิกข้อมูล (Active Uplink Traffic)
3. **ระบบประมวลผลสัญญาณและคลังเก็บ Telemetry (O-RAN RIC & Telemetry Pipeline):**
   * **Near-RT RIC (FlexRIC):** ทำหน้าที่ควบคุม รับส่งข้อมูลบอกประสิทธิภาพผ่านอินเตอร์เฟส E2
   * **T-Tracer telemetry:** สกัดไบนารีตัวอย่างคลื่นวิทยุดิบระดับเศษเสี้ยววินาทีแบบไม่แต่งแต้มสัญญาณ
   * **Closed-Loop Exporter:** สตรีมสัญญาณดิบและสถิติการดึงค่าตำแหน่ง/ RTT ผ่านโปรโตคอล ZeroMQ (ZMQ) ไปยังระบบวิเคราะห์พิกัดเชิงพื้นที่และควบคุมแผงสะท้อน RIS

---

## 📊 2. พารามิเตอร์เชิงฟิสิกส์ที่สามารถสกัดได้ในปัจจุบัน (Extracted Physical Metrics)

ขณะนี้ระบบสามารถถอดรหัสคลื่นวิทยุจริง (Radio Physical Waveform) ออกมาได้สำเร็จแบบเรียลไทม์ และสกัดออกมาเป็นไฟล์ข้อมูลสำหรับ Machine Learning (ML Dataset) ได้แก่:

* **1. RTT Distance (Signed Fractional Level):** ระยะทางการเดินทางไปกลับของคลื่นคำนวณผ่านคณิตศาสตร์ IFFT ร่วมกับ **Parabolic Peak Interpolation** ย่อยแซมเพิล ปลดล็อกความหยาบระดับเซนติเมตร ไม่จำกัดค่าลบ (No Clamping) เพื่อคงสภาพคุณสมบัติการเบี่ยงเบนเฟสในสายนำสัญญาณวิทยุ
* **2. TA Distance (Timing Advance):** ระยะทางประมาณค่าความล่าช้าการเดินสายวิทยุระดับเซนติเมตร โดยประมาณค่าเสถียรต่อเนื่องตาม RTT บนสภาพแวดล้อมฮาร์ดแวร์จริง
* **3. Calibrated RSRP (dBm):** ระดับพลังงานกำลังรับของ USRP ADC ที่ผ่านการ Calibrate ปรับจูนค่า Offset -10.0 dB เพื่อสะท้อนถึงความผันผวนทางกายภาพจริงของสายอากาศ
* **4. Physical Noise-Free SNR (dB):** อัตราส่วนสัญญาณต่อสัญญาณรบกวนที่คำนวณสดจากตัวอย่างคลื่นจริง (First-Order Difference) แทนค่าจำลอง MAC 5 dB ช่วยให้สะท้อนถึงสิ่งกีดขวางและการเปลี่ยนแปลงของระยะทางได้คมชัดระดับ 26-35 dB
* **5. Average IQ Magnitude:** แรงดันเฉลี่ยของคลื่นวิทยุระดับแรงดัน USRP ADC (มีค่าพื้นหลังเฉลี่ยอยู่ที่ 300-380 จากระดับ Thermal Noise Floor)
* **6. Raw IQ Middle 3 (Complex String):** แซมเพิลคลื่นวิทยุย่านพลังงานหลักกึ่งกลาง 3 ซับแคริเออร์หลักเพื่อป้องกัน Guard Band เพื่อใช้ในการแสดงผลและตรวจสอบความปลอดภัยเร่งด่วน
* **7. Raw IQ Full Spectrum (Semicolon Array String):** ข้อมูลสัญญาณ Complex samples ($I+Qj$) ครบถ้วนทุกความถี่เพื่อการประมวลผลเชิงพื้นที่ผ่านโมดูล Deep Learning เช่น `I+Qj;I+Qj;I+Qj;...`

---

## 🛠️ 3. คู่มือปฏิบัติการรันระบบทีละขั้นตอนสำหรับคุณ Beam (Step-by-Step User Guide)

หากคุณ Beam ต้องกลับมาเปิดรันระบบและหน้าจอควบคุมแดชบอร์ดประเมิน RTT/SNR จากเครื่องจริงด้วยตนเอง ให้ทำตามขั้นตอนการเปิดทีละเทอร์มินัลดังนี้ครับ:

### เทอร์มินัล 1: ตรวจสอบและเคลียร์พอร์ตระบบ
ก่อนรัน ตรวจสอบว่าไม่มีโปรเซสเก่าค้างพอร์ต 36421 หรือ 2021:
```bash
sudo pkill -f nearRT-RIC
sudo pkill -f nr-softmodem
sudo pkill -f parse_t_tracer_ris.py
```

### เทอร์มินัล 2: รัน Near-RT RIC (FlexRIC)
```bash
/home/beam/flexric/build/examples/ric/nearRT-RIC
```

### เทอร์มินัล 3: สตาร์ท Telemetry Recorder (T-Tracer)
ทำการลบไฟล์ RAW ข้อมูลดิบเก่า และเปิดระบบดักจับข้อมูลสตรีมคลื่นวิทยุ:
```bash
rm -f /home/beam/.gemini/tmp/demo/L1_metrics_RIS.raw
/home/beam/openairinterface5g/cmake_targets/ran_build/build/common/utils/T/tracer/record \
  -d /home/beam/openairinterface5g/common/utils/T/T_messages.txt \
  -o /home/beam/.gemini/tmp/demo/L1_metrics_RIS.raw \
  -on GNB_PHY_SRS_ESTIMATES_RIS \
  -on GNB_PHY_L1_METRICS_RIS
```

### เทอร์มินัล 4: รันสถานีฐาน gNB (ฮาร์ดแวร์จริง USRP B210)
```bash
echo 'bbEEam167' | sudo -S stdbuf -oL -eL /home/beam/openairinterface5g/cmake_targets/ran_build/build/nr-softmodem \
  -O /home/beam/openairinterface5g/targets/PROJECTS/GENERIC-NR-5GC/CONF/gnb.sa.band78.fr1.106PRB.usrpb210.custom.conf \
  -E --continuous-tx --T_stdout 0
```
*(รอจนสถานีฐานเชื่อมต่อเข้ากับ AMF ของ Core Network เรียบร้อย)*

### เทอร์มินัล 5: เชื่อมต่อและกระตุ้นคลื่นจาก 5G CPE
* เปิดใช้งานอุปกรณ์ 5G CPE ให้เชื่อมต่อและลงทะเบียนเข้าระบบ 5G SA ของสถานีฐาน
* **สำคัญมาก:** เนื่องจาก CPE เชิงพาณิชย์จะจำกัดกำลังส่ง SRS (DTX Mode) เมื่อไม่มีการสตรีมทราฟฟิกขาอัปเพื่อเซฟพลังงาน คุณ Beam จำเป็นต้องสั่งรันคำสั่งยิง Ping ต่อเนื่องจาก CPE เพื่อให้คลื่น SRS ตื่นตัวตลอดเวลา:
```bash
ping -i 0.2 -s 1000 12.1.1.1
```

### เทอร์มินัล 6: รันแดชบอร์ดและการบันทึก ML Dataset
```bash
python3 parse_t_tracer_ris.py
```
* **ผลลัพธ์:** แดชบอร์ด **O-RAN REAL HARDWARE SRS PHYSICAL SPATIAL MONITOR** จะเปิดแสดงผล RTT และ SNR สด พร้อมบันทึกระเบียนข้อมูลลงในคลัง `/home/beam/.gemini/tmp/demo/srs_dataset_real_hardware.csv` โดยอัตโนมัติ!

---

## 🔮 4. แผนระยะยาวสำหรับการใช้งานง่ายที่สุดในอนาคต (Automation & Orchestration Plan)

เพื่อเพิ่มความสะดวกให้คุณ Beam สามารถเริ่มการรันระบบทั้งหมดได้แบบ "คลิกเดียว" (Single-command Launch) โดยไม่ต้องเปิดสลับ 6 หน้าจออีกต่อไป ผมได้วางโครงสร้างแผนพัฒนาระบบตัวช่วยรันดังนี้:

### 1. ระบบควบคุมอัจฉริยะ (Master CLI Bash Script)
เรากำลังจัดทำสคริปต์ `run_real_hardware_pipeline.sh` ซึ่งจะทำงานผ่านโปรแกรมจัดการหน้าต่างเทอร์มินัล `tmux` (Terminal Multiplexer) เมื่อคุณ Beam พิมพ์เพียงคำสั่งเดียว:
```bash
bash run_real_hardware_pipeline.sh
```
สคริปต์จะทำการ:
1. เคลียร์พอร์ต Socket และไฟล์ Raw เก่าให้เองอัตโนมัติ
2. เปิดเทอร์มินัลเบื้องหลัง (Background Windows) รัน RIC, T-Tracer, gNB, และ CPE Telemetry Exporter ตามลำดับความหน่วงเวลาเซฟตี้
3. แบ่งหน้าจอเทอร์มินัลหลักเป็น 2 หน้าต่างคู่กัน (ซ้าย: แสดง Log รวมของ gNB / ขวา: รันและโชว์ แดชบอร์ดความละเอียดสูงอักษร ASCII และกราฟแบบสวยงาม)

### 2. เครื่องมือส่งคำสั่งควบคุมระยะไกล (ZMQ Closed-Loop Automation)
ผสานการสตรีมข้อมูล SNR และ RTT สดจากฮาร์ดแวร์จริงข้ามระบบควบคุมผ่าน **ZMQ Port 5556** สู่โมดูลควบคุมแผงสะท้อนอัจฉริยะ (RIS Control) ในทันทีโดยไม่ต้องควบคุมด้วยตนเอง ช่วยอำนวยความสะดวกในก้าวต่อไปสำหรับการพัฒนาโครงสร้าง Closed-Loop PoC ของคุณ Beam อย่างลื่นไหลและเสถียรที่สุด

---
**จัดทำคู่มือและซอร์สโค้ดโดย:** นายภัทรธร สุภาพ (คุณ Beam)
**สังกัดโครงการ:** O-RAN 5G Real Hardware Telemetry and RIS Optimization
