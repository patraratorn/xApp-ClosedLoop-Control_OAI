#!/bin/bash

# ======================================================================
# JAVIS: RUN TELEMETRY RECORDER
# ======================================================================
# สคริปต์นี้จะดักจับเฉพาะข้อมูลพิกัด (L1 Metrics) และคลื่นดิบ (SRS Estimates)
# เพื่อป้องกันปัญหา gNB ค้าง (T cache is full)

echo "📡 Starting OAI Telemetry Recorder..."
echo "✅ บล็อกข้อมูลขยะสำเร็จ"
echo "✅ ดึงเฉพาะ GNB_PHY_UL_FREQ_CHANNEL_ESTIMATE (SRS)"
echo "✅ ดึงเฉพาะ GNB_PHY_L1_METRICS_RIS (พิกัด RNTI)"
echo "--------------------------------------------------------"

/home/beam/openairinterface5g/cmake_targets/ran_build/build/common/utils/T/tracer/record \
  -d /home/beam/openairinterface5g/common/utils/T/T_messages.txt \
  -o /home/beam/.gemini/tmp/demo/L1_metrics_RIS.raw \
  -on GNB_PHY_SRS_ESTIMATES_RIS \
  -on GNB_PHY_L1_METRICS_RIS
