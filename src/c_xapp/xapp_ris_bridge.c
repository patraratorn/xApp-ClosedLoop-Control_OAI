#include "../../../../src/xApp/e42_xapp_api.h"
#include "../../../../src/util/time_now_us.h"
#include <stdlib.h>
#include <stdio.h>
#include <time.h>
#include <unistd.h>
#include <pthread.h>
#include <zmq.h>

void *zmq_ctx = NULL; void *zmq_pub = NULL;
static e2_node_arr_xapp_t global_nodes;

static void sm_cb_kpm(sm_ag_if_rd_t const* rd) {
    if (rd->type != INDICATION_MSG_AGENT_IF_ANS_V0) return;
    kpm_ind_data_t const* ind = &rd->ind.kpm.ind;
    
    if (ind->msg.type == FORMAT_3_INDICATION_MESSAGE) {
        kpm_ind_msg_format_3_t const* msg3 = &ind->msg.frm_3;
        for (size_t i = 0; i < msg3->ue_meas_report_lst_len; i++) {
            kpm_ind_msg_format_1_t const* frm1 = &msg3->meas_report_per_ue[i].ind_msg_format_1;
            // Access member 'ue_meas_report_lst' instead of 'ue_id_e2sm'
            uint64_t ue_id = msg3->meas_report_per_ue[i].ue_meas_report_lst.gnb.amf_ue_ngap_id;
            
            char payload[1024];
            int pos = snprintf(payload, 1024, "{\"ue_id\": %lu", ue_id);
            
            for (size_t j = 0; j < frm1->meas_info_lst_len; j++) {
                char *name = cp_ba_to_str(frm1->meas_info_lst[j].meas_type.name);
                double val = (frm1->meas_data_lst[0].meas_record_lst[j].value == REAL_MEAS_VALUE) ? 
                             frm1->meas_data_lst[0].meas_record_lst[j].real_val : 
                             (double)frm1->meas_data_lst[0].meas_record_lst[j].int_val;
                
                pos += snprintf(payload + pos, 1024 - pos, ", \"%s\": %.2f", name, val);
                free(name);
            }
            snprintf(payload + pos, 1024 - pos, "}");
            
            zmq_send(zmq_pub, payload, strlen(payload), 0);
            printf("[RIS-BRIDGE] Dispatching Layer Data: %s\n", payload);
        }
    }
}

static kpm_sub_data_t gen_kpm_subs_ris(void) {
    kpm_sub_data_t kpm_sub = {0};
    kpm_sub.ev_trg_def.type = FORMAT_1_RIC_EVENT_TRIGGER;
    kpm_sub.ev_trg_def.kpm_ric_event_trigger_format_1.report_period_ms = 2000;
    
    kpm_sub.sz_ad = 1;
    kpm_sub.ad = calloc(1, sizeof(kpm_act_def_t));
    kpm_sub.ad[0].type = FORMAT_4_ACTION_DEFINITION;
    
    kpm_sub.ad[0].frm_4.matching_cond_lst_len = 1;
    kpm_sub.ad[0].frm_4.matching_cond_lst = calloc(1, sizeof(matching_condition_format_4_lst_t));
    kpm_sub.ad[0].frm_4.matching_cond_lst[0].test_info_lst.test_cond_type = S_NSSAI_TEST_COND_TYPE;
    kpm_sub.ad[0].frm_4.matching_cond_lst[0].test_info_lst.S_NSSAI = TRUE_TEST_COND_TYPE;
    kpm_sub.ad[0].frm_4.matching_cond_lst[0].test_info_lst.test_cond = calloc(1, sizeof(test_cond_e));
    *kpm_sub.ad[0].frm_4.matching_cond_lst[0].test_info_lst.test_cond = EQUAL_TEST_COND;
    kpm_sub.ad[0].frm_4.matching_cond_lst[0].test_info_lst.test_cond_value = calloc(1, sizeof(test_cond_value_t));
    kpm_sub.ad[0].frm_4.matching_cond_lst[0].test_info_lst.test_cond_value->type = OCTET_STRING_TEST_COND_VALUE;
    kpm_sub.ad[0].frm_4.matching_cond_lst[0].test_info_lst.test_cond_value->octet_string_value = calloc(1, sizeof(byte_array_t));
    uint8_t nssai_buf[] = {0x01, 0xFF, 0xFF, 0xFF};
    kpm_sub.ad[0].frm_4.matching_cond_lst[0].test_info_lst.test_cond_value->octet_string_value->buf = malloc(4);
    memcpy(kpm_sub.ad[0].frm_4.matching_cond_lst[0].test_info_lst.test_cond_value->octet_string_value->buf, nssai_buf, 4);
    kpm_sub.ad[0].frm_4.matching_cond_lst[0].test_info_lst.test_cond_value->octet_string_value->len = 4;

    kpm_sub.ad[0].frm_4.action_def_format_1.gran_period_ms = 2000;
    kpm_sub.ad[0].frm_4.action_def_format_1.meas_info_lst_len = 3;
    kpm_sub.ad[0].frm_4.action_def_format_1.meas_info_lst = calloc(3, sizeof(meas_info_format_1_lst_t));
    
    char* names[] = {"DRB.UEThpDl", "RRU.PrbTotDl", "DRB.RlcSduDelayDl"};
    for (int i = 0; i < 3; i++) {
        kpm_sub.ad[0].frm_4.action_def_format_1.meas_info_lst[i].meas_type.type = NAME_MEAS_TYPE;
        kpm_sub.ad[0].frm_4.action_def_format_1.meas_info_lst[i].meas_type.name = cp_str_to_ba(names[i]);
        kpm_sub.ad[0].frm_4.action_def_format_1.meas_info_lst[i].label_info_lst_len = 1;
        kpm_sub.ad[0].frm_4.action_def_format_1.meas_info_lst[i].label_info_lst = calloc(1, sizeof(label_info_lst_t));
        kpm_sub.ad[0].frm_4.action_def_format_1.meas_info_lst[i].label_info_lst[0].noLabel = calloc(1, sizeof(enum_value_e));
        *kpm_sub.ad[0].frm_4.action_def_format_1.meas_info_lst[i].label_info_lst[0].noLabel = TRUE_ENUM_VALUE;
    }
    return kpm_sub;
}

int main(int argc, char* argv[]) {
    fr_args_t args = init_fr_args(argc, argv);
    zmq_ctx = zmq_ctx_new(); zmq_pub = zmq_socket(zmq_ctx, ZMQ_PUB); zmq_bind(zmq_pub, "tcp://*:5555");
    init_xapp_api(&args); sleep(1);
    global_nodes = e2_nodes_xapp_api();
    
    for (size_t i = 0; i < global_nodes.len; ++i) {
        kpm_sub_data_t kpm_sub = gen_kpm_subs_ris();
        report_sm_xapp_api(&global_nodes.n[i].id, 2, &kpm_sub, sm_cb_kpm);
    }
    printf("[*] RIS-BRIDGE xApp ACTIVE. Collecting data for FPGA Bridge...\n");
    while(1) { sleep(10); }
    return 0;
}
