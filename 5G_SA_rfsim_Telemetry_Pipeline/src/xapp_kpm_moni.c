#include "../../../../src/xApp/e42_xapp_api.h"
#include "../../../../src/util/alg_ds/alg/defer.h"
#include "../../../../src/util/time_now_us.h"
#include "../../../../src/util/alg_ds/ds/lock_guard/lock_guard.h"
#include <stdlib.h>
#include <stdio.h>
#include <time.h>
#include <unistd.h>
#include <signal.h>
#include <pthread.h>
#include <zmq.h>

static void *zmq_ctx = NULL; static void *zmq_pub = NULL;

static void sm_cb_kpm(sm_ag_if_rd_t const* rd) {
    assert(rd != NULL);
    if (rd->type != INDICATION_MSG_AGENT_IF_ANS_V0) return;
    kpm_ind_data_t const* ind = &rd->ind.kpm.ind;
    
    if (ind->msg.type == FORMAT_1_INDICATION_MESSAGE) {
        kpm_ind_msg_format_1_t const* msg1 = &ind->msg.frm_1;
        for (size_t i = 0; i < msg1->meas_info_lst_len; i++) {
            char *name = cp_ba_to_str(msg1->meas_info_lst[i].meas_type.name);
            for (size_t j = 0; j < msg1->meas_data_lst_len; j++) {
                double val = (msg1->meas_data_lst[j].meas_record_lst[i].value == REAL_MEAS_VALUE) ? 
                             msg1->meas_data_lst[j].meas_record_lst[i].real_val : 
                             (double)msg1->meas_data_lst[j].meas_record_lst[i].int_val;
                char payload[512];
                snprintf(payload, 511, "{\"meas_name\": \"%s\", \"value\": %.2f, \"ue_id\": 1}", name, val);
                zmq_send(zmq_pub, payload, strlen(payload), 0);
            }
            free(name);
        }
    } else if (ind->msg.type == FORMAT_3_INDICATION_MESSAGE) {
        kpm_ind_msg_format_3_t const* msg3 = &ind->msg.frm_3;
        for (size_t i = 0; i < msg3->ue_meas_report_lst_len; i++) {
            kpm_ind_msg_format_1_t const* frm1 = &msg3->meas_report_per_ue[i].ind_msg_format_1;
            for (size_t j = 0; j < frm1->meas_info_lst_len; j++) {
                char *name = cp_ba_to_str(frm1->meas_info_lst[j].meas_type.name);
                double val = (frm1->meas_data_lst[0].meas_record_lst[j].value == REAL_MEAS_VALUE) ? 
                             frm1->meas_data_lst[0].meas_record_lst[j].real_val : 
                             (double)frm1->meas_data_lst[0].meas_record_lst[j].int_val;
                char payload[512];
                snprintf(payload, 511, "{\"meas_name\": \"%s\", \"value\": %.2f, \"ue_id\": %lu}", name, val, msg3->meas_report_per_ue[i].ue_meas_report_lst.gnb.amf_ue_ngap_id);
                zmq_send(zmq_pub, payload, strlen(payload), 0);
                free(name);
            }
        }
    }
}

static kpm_sub_data_t gen_kpm_subs_no_filter(void) {
    kpm_sub_data_t kpm_sub = {0};
    kpm_sub.ev_trg_def.type = FORMAT_1_RIC_EVENT_TRIGGER;
    kpm_sub.ev_trg_def.kpm_ric_event_trigger_format_1.report_period_ms = 1000;
    kpm_sub.sz_ad = 1;
    kpm_sub.ad = calloc(1, sizeof(kpm_act_def_t));
    
    kpm_sub.ad[0].type = FORMAT_1_ACTION_DEFINITION;
    kpm_sub.ad[0].frm_1.gran_period_ms = 1000;
    
    const char* metrics[] = {
        "DRB.UEThpDl", "DRB.UEThpUl", "RRU.PrbTotDl", "RRU.PrbTotUl"
    };
    size_t num_metrics = 4;
    kpm_sub.ad[0].frm_1.meas_info_lst_len = num_metrics;
    kpm_sub.ad[0].frm_1.meas_info_lst = calloc(num_metrics, sizeof(meas_info_format_1_lst_t));
    for(size_t i=0; i<num_metrics; ++i) {
        kpm_sub.ad[0].frm_1.meas_info_lst[i].meas_type.type = NAME_MEAS_TYPE;
        kpm_sub.ad[0].frm_1.meas_info_lst[i].meas_type.name = cp_str_to_ba(metrics[i]);
        kpm_sub.ad[0].frm_1.meas_info_lst[i].label_info_lst_len = 1;
        kpm_sub.ad[0].frm_1.meas_info_lst[i].label_info_lst = calloc(1, sizeof(label_info_lst_t));
        kpm_sub.ad[0].frm_1.meas_info_lst[i].label_info_lst[0].noLabel = calloc(1, sizeof(enum_value_e));
        *kpm_sub.ad[0].frm_1.meas_info_lst[i].label_info_lst[0].noLabel = TRUE_ENUM_VALUE;
    }
    return kpm_sub;
}

int main(int argc, char* argv[]) {
    printf("[*] Starting Stable RIS xApp (Format 1 - No Filter) with SRS IQ\n");
    zmq_ctx = zmq_ctx_new();
    zmq_pub = zmq_socket(zmq_ctx, ZMQ_PUB);
    zmq_bind(zmq_pub, "tcp://*:5555");
    
    fr_args_t args = init_fr_args(argc, argv);
    init_xapp_api(&args);
    sleep(1);
    e2_node_arr_xapp_t nodes = e2_nodes_xapp_api();
    if (nodes.len > 0) {
        printf("[+] Connected to Node %d\n", nodes.n[0].id.nb_id.nb_id);
        kpm_sub_data_t sub = gen_kpm_subs_no_filter();
        report_sm_xapp_api(&nodes.n[0].id, nodes.n[0].rf[0].id, &sub, sm_cb_kpm);
    }
    while(1) sleep(1);
    return 0;
}
