/*
 * SPDX-License-Identifier: LicenseRef-CSSL-1.0
 */

#include "ran_func_kpm_subs.h"
#include <search.h>
#include <string.h>
#include <stdio.h>
#include <assert.h>
#include "common/utils/T/T.h"
#include "common/utils/T/T_IDs.h"

// Access OAI Global context for UE recovery
#include "NR_MAC_gNB/mac_proto.h"
extern RAN_CONTEXT_t RC;
extern c16_t g_srs_iq_buffer[1024];
extern pthread_mutex_t g_srs_iq_mutex;

e2_node_level_stats_t cp_node_level_stats(const e2_node_level_stats_t *src)
{
  e2_node_level_stats_t dst = {0};
  if (src) {
    dst.mac_stats.dl.total_prb_aggregate = src->mac_stats.dl.total_prb_aggregate,
    dst.mac_stats.dl.used_prb_aggregate = src->mac_stats.dl.used_prb_aggregate,
    dst.mac_stats.ul.total_prb_aggregate = src->mac_stats.ul.total_prb_aggregate,
    dst.mac_stats.ul.used_prb_aggregate = src->mac_stats.ul.used_prb_aggregate;
  }
  return dst;
}

static meas_record_lst_t fill_dummy_int(const label_info_lst_t label, uint32_t gran_period_ms, cudu_ue_info_pair_t ue_info, const size_t ue_idx, e2_node_level_stats_t* node_stats) {
  meas_record_lst_t meas_record = {0};
  meas_record.value = INTEGER_MEAS_VALUE;
  meas_record.int_val = 0;
  return meas_record;
}

static meas_record_lst_t fill_DRB_UE_RSRP(const label_info_lst_t label, uint32_t gran_period_ms, cudu_ue_info_pair_t ue_info, const size_t ue_idx, e2_node_level_stats_t* node_stats)
{
  meas_record_lst_t meas_record = {0};
  meas_record.value = REAL_MEAS_VALUE;
#if defined (NGRAN_GNB_DU)
  if (ue_info.ue != NULL) {
    meas_record.real_val = (ue_info.ue->mac_stats.num_rsrp_meas > 0) ? (float)ue_info.ue->mac_stats.cumul_rsrp / ue_info.ue->mac_stats.num_rsrp_meas : 0.0f;
  } else {
    meas_record.real_val = 0.0f;
  }
#else
  meas_record.real_val = 0.0f;
#endif
  return meas_record;
}

static meas_record_lst_t fill_DRB_UE_SNR(const label_info_lst_t label, uint32_t gran_period_ms, cudu_ue_info_pair_t ue_info, const size_t ue_idx, e2_node_level_stats_t* node_stats)
{
  meas_record_lst_t meas_record = {0};
  meas_record.value = REAL_MEAS_VALUE;
#if defined (NGRAN_GNB_DU)
  if (ue_info.ue != NULL) {
    meas_record.real_val = nr_mac_get_snr(&ue_info.ue->UE_sched_ctrl.pusch_pc);
  } else {
    meas_record.real_val = 0.0f;
  }
#else
  meas_record.real_val = 0.0f;
#endif
  return meas_record;
}

static meas_record_lst_t fill_DRB_UE_BeamIdx(const label_info_lst_t label, uint32_t gran_period_ms, cudu_ue_info_pair_t ue_info, const size_t ue_idx, e2_node_level_stats_t* node_stats)
{
  meas_record_lst_t meas_record = {0};
  meas_record.value = INTEGER_MEAS_VALUE;
  if (ue_info.ue != NULL) {
    meas_record.int_val = (uint32_t)ue_info.ue->UE_beam_index;
  } else {
    meas_record.int_val = 0;
  }
  return meas_record;
}

// Function to pack 16-bit I and Q into a 32-bit integer
static uint32_t pack_iq(c16_t sample) {
    return ((uint32_t)(uint16_t)sample.r << 16) | (uint32_t)(uint16_t)sample.i;
}

#define GEN_FILL_SRS_IQ(idx) \
static meas_record_lst_t fill_DRB_UE_SRS_IQ_##idx(const label_info_lst_t label, uint32_t gran_period_ms, cudu_ue_info_pair_t ue_info, const size_t ue_idx, e2_node_level_stats_t* node_stats) { \
  meas_record_lst_t meas_record = {0}; \
  meas_record.value = INTEGER_MEAS_VALUE; \
  pthread_mutex_lock(&g_srs_iq_mutex); \
  meas_record.int_val = pack_iq(g_srs_iq_buffer[idx]); \
  pthread_mutex_unlock(&g_srs_iq_mutex); \
  return meas_record; \
}

GEN_FILL_SRS_IQ(0)
GEN_FILL_SRS_IQ(1)
GEN_FILL_SRS_IQ(2)
GEN_FILL_SRS_IQ(3)
GEN_FILL_SRS_IQ(4)
GEN_FILL_SRS_IQ(5)
GEN_FILL_SRS_IQ(6)
GEN_FILL_SRS_IQ(7)
GEN_FILL_SRS_IQ(8)
GEN_FILL_SRS_IQ(9)
GEN_FILL_SRS_IQ(10)
GEN_FILL_SRS_IQ(11)
GEN_FILL_SRS_IQ(12)
GEN_FILL_SRS_IQ(13)
GEN_FILL_SRS_IQ(14)
GEN_FILL_SRS_IQ(15)

static meas_record_lst_t fill_DRB_UE_TA(const label_info_lst_t label, uint32_t gran_period_ms, cudu_ue_info_pair_t ue_info, const size_t ue_idx, e2_node_level_stats_t* node_stats)
{
  meas_record_lst_t meas_record = {0};
  meas_record.value = INTEGER_MEAS_VALUE;
  if (ue_info.ue != NULL) {
    meas_record.int_val = (uint32_t)ue_info.ue->UE_sched_ctrl.ta_update;
  } else {
    meas_record.int_val = 0;
  }
  return meas_record;
}

static kv_measure_t lst_measure[] = {
  {.key = "DRB.UE.RSRP", .value = fill_DRB_UE_RSRP },
  {.key = "DRB.UE.SINR", .value = fill_DRB_UE_SNR },
  {.key = "DRB.UE.SNR", .value = fill_DRB_UE_SNR },
  {.key = "DRB.UE.BeamIdx", .value = fill_DRB_UE_BeamIdx },
  {.key = "DRB.UE.TA", .value = fill_DRB_UE_TA },
  {.key = "DRB.PdcpSduVolumeDL", .value = fill_dummy_int }, 
  {.key = "DRB.PdcpSduVolumeUL", .value = fill_dummy_int },
  {.key = "RRU.PrbTotDl", .value = fill_dummy_int }, 
  {.key = "DRB.UE.SRS_IQ_0", .value = fill_DRB_UE_SRS_IQ_0 },
  {.key = "DRB.UE.SRS_IQ_1", .value = fill_DRB_UE_SRS_IQ_1 },
  {.key = "DRB.UE.SRS_IQ_2", .value = fill_DRB_UE_SRS_IQ_2 },
  {.key = "DRB.UE.SRS_IQ_3", .value = fill_DRB_UE_SRS_IQ_3 },
  {.key = "DRB.UE.SRS_IQ_4", .value = fill_DRB_UE_SRS_IQ_4 },
  {.key = "DRB.UE.SRS_IQ_5", .value = fill_DRB_UE_SRS_IQ_5 },
  {.key = "DRB.UE.SRS_IQ_6", .value = fill_DRB_UE_SRS_IQ_6 },
  {.key = "DRB.UE.SRS_IQ_7", .value = fill_DRB_UE_SRS_IQ_7 },
  {.key = "DRB.UE.SRS_IQ_8", .value = fill_DRB_UE_SRS_IQ_8 },
  {.key = "DRB.UE.SRS_IQ_9", .value = fill_DRB_UE_SRS_IQ_9 },
  {.key = "DRB.UE.SRS_IQ_10", .value = fill_DRB_UE_SRS_IQ_10 },
  {.key = "DRB.UE.SRS_IQ_11", .value = fill_DRB_UE_SRS_IQ_11 },
  {.key = "DRB.UE.SRS_IQ_12", .value = fill_DRB_UE_SRS_IQ_12 },
  {.key = "DRB.UE.SRS_IQ_13", .value = fill_DRB_UE_SRS_IQ_13 },
  {.key = "DRB.UE.SRS_IQ_14", .value = fill_DRB_UE_SRS_IQ_14 },
  {.key = "DRB.UE.SRS_IQ_15", .value = fill_DRB_UE_SRS_IQ_15 },
}; 

void init_kpm_subs_data(void)
{


  const size_t ht_len = sizeof(lst_measure) / sizeof(lst_measure[0]);
  hcreate(ht_len);
  ENTRY kv_pair;
  for (size_t i = 0; i < ht_len; i++) {
    kv_pair.key = lst_measure[i].key;
    kv_pair.data = &lst_measure[i];
    hsearch(kv_pair, ENTER);
  }
}

meas_record_lst_t get_kpm_meas_value(char* kpm_meas_name, const label_info_lst_t label, uint32_t gran_period_ms, cudu_ue_info_pair_t ue_info, const size_t ue_idx, e2_node_level_stats_t* node_stats)
{
  if (kpm_meas_name == NULL) {
    meas_record_lst_t r = {0};
    return r;
  }

  ENTRY search_entry = {.key = kpm_meas_name};
  ENTRY *found_entry = hsearch(search_entry, FIND);
  if (found_entry == NULL) {
    meas_record_lst_t r = {0};
    return r;
  }

  kv_measure_t *kv_found = (kv_measure_t *)found_entry->data;
  meas_record_lst_t meas_record = kv_found->value(label, gran_period_ms, ue_info, ue_idx, node_stats);

  // --- UE RECOVERY & T_TRACER INJECTION ---
#if defined (NGRAN_GNB_DU)
  if (strcmp(kpm_meas_name, "DRB.UE.TA") == 0) {
    NR_UE_info_t* active_ue = ue_info.ue;
    
    // If E2 Agent lost UE pointer, try to find it in MAC directly
    if (active_ue == NULL && RC.nrmac != NULL && RC.nrmac[0] != NULL) {
        // Fallback to the first active UE in the system for this demo
        NR_UEs_t *UE_list = &RC.nrmac[0]->UE_info;
        for (int i = 0; i < MAX_MOBILES_PER_GNB; i++) {
            if (UE_list->connected_ue_list[i] != NULL) {
                active_ue = UE_list->connected_ue_list[i];
                break;
            }
        }
    }

    if (active_ue != NULL) {
        int ue_id = (int)active_ue->rnti;
        int ta = (int)active_ue->UE_sched_ctrl.ta_update;
        float dist_m = (float)((ta * 299792458.0) / (2.0 * 46.08e6));
        float rsrp = (active_ue->mac_stats.num_rsrp_meas > 0) ? (float)active_ue->mac_stats.cumul_rsrp / active_ue->mac_stats.num_rsrp_meas : 0.0f;
        int snr = (int)nr_mac_get_snr(&active_ue->UE_sched_ctrl.pusch_pc);
        int beam_id = (int)active_ue->UE_beam_index;

        printf("[KPM RIS] SUCCESS: Pushing spatial data for RNTI %04x (Dist: %.2fm)\n", ue_id, dist_m);
        T(T_GNB_PHY_L1_METRICS_RIS, T_INT(ue_id), T_FLOAT(dist_m), T_FLOAT(rsrp), T_INT(snr), T_INT(beam_id));
    } else {
        // Only print error once in a while to keep log clean
        static int skip = 0;
        if (skip++ % 10 == 0) printf("[KPM RIS] WARNING: No active UE found in MAC or E2 Agent.\n");
    }
  }
#endif

  return meas_record;
}
