#include "../../../../src/xApp/e42_xapp_api.h"
#include "../../../../src/util/alg_ds/alg/defer.h"
#include "../../../../src/sm/rc_sm/ie/ir/ran_param_struct.h"
#include "../../../../src/sm/rc_sm/ie/ir/ran_param_list.h"
#include "../../../../src/util/time_now_us.h"
#include "../../../../src/util/alg_ds/alg/murmur_hash_32.h"
#include "../../../../src/util/alg_ds/ds/lock_guard/lock_guard.h"
#include "../../../../src/util/alg_ds/ds/assoc_container/assoc_generic.h"
#include "../../../../src/util/e.h"
#include <stdlib.h>
#include <stdio.h>
#include <time.h>
#include <unistd.h>
#include <signal.h>
#include <pthread.h>
#include <zmq.h>

static pthread_mutex_t mtx;
static e2_node_arr_xapp_t global_nodes;
static int const RC_ran_function = 3;
static void *zmq_ctx = NULL; static void *zmq_pub = NULL;

static seq_ran_param_t fill_drb_id_param(void) {
  seq_ran_param_t drb_param = {0};
  drb_param.ran_param_id = 1; 
  drb_param.ran_param_val.type = ELEMENT_KEY_FLAG_TRUE_RAN_PARAMETER_VAL_TYPE;
  drb_param.ran_param_val.flag_true = calloc(1, sizeof(ran_parameter_value_t));
  drb_param.ran_param_val.flag_true->type = INTEGER_RAN_PARAMETER_VALUE;
  drb_param.ran_param_val.flag_true->int_ran = 5; 
  return drb_param;
}

static seq_ran_param_t fill_qos_flows_param(void) {
  seq_ran_param_t qos_param = {0};
  qos_param.ran_param_id = 2; 
  qos_param.ran_param_val.type = LIST_RAN_PARAMETER_VAL_TYPE;
  qos_param.ran_param_val.lst = calloc(1, sizeof(ran_param_list_t));
  ran_param_list_t* rpl = qos_param.ran_param_val.lst;
  rpl->sz_lst_ran_param = 1;
  rpl->lst_ran_param = calloc(1, sizeof(lst_ran_param_t));
  rpl->lst_ran_param[0].ran_param_struct.sz_ran_param_struct = 2;
  rpl->lst_ran_param[0].ran_param_struct.ran_param_struct = calloc(2, sizeof(seq_ran_param_t));
  rpl->lst_ran_param[0].ran_param_struct.ran_param_struct[0].ran_param_id = 4; 
  rpl->lst_ran_param[0].ran_param_struct.ran_param_struct[0].ran_param_val.type = ELEMENT_KEY_FLAG_TRUE_RAN_PARAMETER_VAL_TYPE;
  rpl->lst_ran_param[0].ran_param_struct.ran_param_struct[0].ran_param_val.flag_true = calloc(1, sizeof(ran_parameter_value_t));
  rpl->lst_ran_param[0].ran_param_struct.ran_param_struct[0].ran_param_val.flag_true->type = INTEGER_RAN_PARAMETER_VALUE;
  rpl->lst_ran_param[0].ran_param_struct.ran_param_struct[0].ran_param_val.flag_true->int_ran = 10; 
  rpl->lst_ran_param[0].ran_param_struct.ran_param_struct[1].ran_param_id = 5; 
  rpl->lst_ran_param[0].ran_param_struct.ran_param_struct[1].ran_param_val.type = ELEMENT_KEY_FLAG_FALSE_RAN_PARAMETER_VAL_TYPE;
  rpl->lst_ran_param[0].ran_param_struct.ran_param_struct[1].ran_param_val.flag_false = calloc(1, sizeof(ran_parameter_value_t));
  rpl->lst_ran_param[0].ran_param_struct.ran_param_struct[1].ran_param_val.flag_false->type = INTEGER_RAN_PARAMETER_VALUE;
  rpl->lst_ran_param[0].ran_param_struct.ran_param_struct[1].ran_param_val.flag_false->int_ran = 1; 
  return qos_param;
}

static rc_ctrl_req_data_t gen_rc_ctrl_msg(void) {
    rc_ctrl_req_data_t rc_ctrl = {0};
    rc_ctrl.hdr.format = FORMAT_1_E2SM_RC_CTRL_HDR;
    rc_ctrl.hdr.frmt_1.ric_style_type = 1;
    rc_ctrl.hdr.frmt_1.ctrl_act_id = 2;
    rc_ctrl.hdr.frmt_1.ue_id.type = GNB_UE_ID_E2SM;
    rc_ctrl.hdr.frmt_1.ue_id.gnb.amf_ue_ngap_id = 1; 
    rc_ctrl.hdr.frmt_1.ue_id.gnb.gnb_cu_ue_f1ap_lst_len = 1;
    rc_ctrl.hdr.frmt_1.ue_id.gnb.gnb_cu_ue_f1ap_lst = calloc(1, sizeof(uint32_t));
    rc_ctrl.hdr.frmt_1.ue_id.gnb.gnb_cu_ue_f1ap_lst[0] = 1;
    rc_ctrl.msg.format = FORMAT_1_E2SM_RC_CTRL_MSG;
    rc_ctrl.msg.frmt_1.sz_ran_param = 2;
    rc_ctrl.msg.frmt_1.ran_param = calloc(2, sizeof(seq_ran_param_t));
    rc_ctrl.msg.frmt_1.ran_param[0] = fill_drb_id_param();
    rc_ctrl.msg.frmt_1.ran_param[1] = fill_qos_flows_param();
    return rc_ctrl;
}

void *zmq_control_thread(void *arg) {
    (void)arg; void *ctx = zmq_ctx_new(); void *sub = zmq_socket(ctx, ZMQ_SUB);
    zmq_connect(sub, "tcp://127.0.0.1:5556"); zmq_setsockopt(sub, ZMQ_SUBSCRIBE, "", 0);
    while(1) {
        char buffer[512]; int bytes = zmq_recv(sub, buffer, 511, 0);
        if (bytes > 0) {
            buffer[bytes] = '\0';
            lock_guard(&mtx);
            for (size_t i = 0; i < global_nodes.len; ++i) {
                e2_node_connected_xapp_t* n = &global_nodes.n[i];
                for (size_t j = 0; j < n->len_rf; j++) {
                    if (n->rf[j].id == RC_ran_function) {
                        rc_ctrl_req_data_t rc_ctrl = gen_rc_ctrl_msg();
                        control_sm_xapp_api(&n->id, RC_ran_function, &rc_ctrl);
                    }
                }
            }
        }
    }
    return NULL;
}

static void sm_cb_kpm(sm_ag_if_rd_t const* rd) {
    assert(rd != NULL);
    if (rd->type != INDICATION_MSG_AGENT_IF_ANS_V0) return;
    kpm_ind_data_t const* ind = &rd->ind.kpm.ind;
    if (ind->msg.type == FORMAT_3_INDICATION_MESSAGE) {
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

static kpm_sub_data_t gen_kpm_subs_stable(void) {
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
    kpm_sub.ad[0].frm_4.action_def_format_1.meas_info_lst_len = 4;
    kpm_sub.ad[0].frm_4.action_def_format_1.meas_info_lst = calloc(4, sizeof(meas_info_format_1_lst_t));
    
    // 0: DRB.UE.RSRP
    kpm_sub.ad[0].frm_4.action_def_format_1.meas_info_lst[0].meas_type.type = NAME_MEAS_TYPE;
    kpm_sub.ad[0].frm_4.action_def_format_1.meas_info_lst[0].meas_type.name = cp_str_to_ba("DRB.UE.RSRP");
    kpm_sub.ad[0].frm_4.action_def_format_1.meas_info_lst[0].label_info_lst_len = 1;
    kpm_sub.ad[0].frm_4.action_def_format_1.meas_info_lst[0].label_info_lst = calloc(1, sizeof(label_info_lst_t));
    kpm_sub.ad[0].frm_4.action_def_format_1.meas_info_lst[0].label_info_lst[0].noLabel = calloc(1, sizeof(enum_value_e));
    *kpm_sub.ad[0].frm_4.action_def_format_1.meas_info_lst[0].label_info_lst[0].noLabel = TRUE_ENUM_VALUE;

    // 1: DRB.UE.SNR
    kpm_sub.ad[0].frm_4.action_def_format_1.meas_info_lst[1].meas_type.type = NAME_MEAS_TYPE;
    kpm_sub.ad[0].frm_4.action_def_format_1.meas_info_lst[1].meas_type.name = cp_str_to_ba("DRB.UE.SNR");
    kpm_sub.ad[0].frm_4.action_def_format_1.meas_info_lst[1].label_info_lst_len = 1;
    kpm_sub.ad[0].frm_4.action_def_format_1.meas_info_lst[1].label_info_lst = calloc(1, sizeof(label_info_lst_t));
    kpm_sub.ad[0].frm_4.action_def_format_1.meas_info_lst[1].label_info_lst[0].noLabel = calloc(1, sizeof(enum_value_e));
    *kpm_sub.ad[0].frm_4.action_def_format_1.meas_info_lst[1].label_info_lst[0].noLabel = TRUE_ENUM_VALUE;

    // 2: DRB.UE.BeamIdx
    kpm_sub.ad[0].frm_4.action_def_format_1.meas_info_lst[2].meas_type.type = NAME_MEAS_TYPE;
    kpm_sub.ad[0].frm_4.action_def_format_1.meas_info_lst[2].meas_type.name = cp_str_to_ba("DRB.UE.BeamIdx");
    kpm_sub.ad[0].frm_4.action_def_format_1.meas_info_lst[2].label_info_lst_len = 1;
    kpm_sub.ad[0].frm_4.action_def_format_1.meas_info_lst[2].label_info_lst = calloc(1, sizeof(label_info_lst_t));
    kpm_sub.ad[0].frm_4.action_def_format_1.meas_info_lst[2].label_info_lst[0].noLabel = calloc(1, sizeof(enum_value_e));
    *kpm_sub.ad[0].frm_4.action_def_format_1.meas_info_lst[2].label_info_lst[0].noLabel = TRUE_ENUM_VALUE;

    // 3: DRB.UE.TA
    kpm_sub.ad[0].frm_4.action_def_format_1.meas_info_lst[3].meas_type.type = NAME_MEAS_TYPE;
    kpm_sub.ad[0].frm_4.action_def_format_1.meas_info_lst[3].meas_type.name = cp_str_to_ba("DRB.UE.TA");
    kpm_sub.ad[0].frm_4.action_def_format_1.meas_info_lst[3].label_info_lst_len = 1;
    kpm_sub.ad[0].frm_4.action_def_format_1.meas_info_lst[3].label_info_lst = calloc(1, sizeof(label_info_lst_t));
    kpm_sub.ad[0].frm_4.action_def_format_1.meas_info_lst[3].label_info_lst[0].noLabel = calloc(1, sizeof(enum_value_e));
    *kpm_sub.ad[0].frm_4.action_def_format_1.meas_info_lst[3].label_info_lst[0].noLabel = TRUE_ENUM_VALUE;

    return kpm_sub;
}

int main(int argc, char* argv[]) {
    fr_args_t args = init_fr_args(argc, argv);
    zmq_ctx = zmq_ctx_new(); zmq_pub = zmq_socket(zmq_ctx, ZMQ_PUB); zmq_bind(zmq_pub, "tcp://*:5555");
    pthread_t control_tid; pthread_create(&control_tid, NULL, zmq_control_thread, NULL);
    init_xapp_api(&args); sleep(1);
    global_nodes = e2_nodes_xapp_api();
    pthread_mutexattr_t attr; pthread_mutexattr_init(&attr); pthread_mutex_init(&mtx, &attr);
    int const KPM_ran_function = 2;
    for (size_t i = 0; i < global_nodes.len; ++i) {
        e2_node_connected_xapp_t* n = &global_nodes.n[i];
        for (size_t j = 0; j < n->len_rf; j++) {
            if (n->rf[j].id == KPM_ran_function) {
                kpm_sub_data_t kpm_sub = gen_kpm_subs_stable();
                report_sm_xapp_api(&n->id, KPM_ran_function, &kpm_sub, sm_cb_kpm);
                printf("[KPM] Hardware Stable Subscription (2000ms) on Node %u\n", n->id.nb_id.nb_id);
            }
        }
    }
    printf("[*] STABLE xApp (2s interval) started. Waiting for data...\n");
    while(1) { sleep(10); }
    return 0;
}
