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

typedef enum { QoS_flow_mapping_configuration_7_6_2_1 = 2 } rc_ctrl_service_style_1_e;
void *zmq_ctx = NULL; void *zmq_pub = NULL;
static pthread_mutex_t mtx;
static e2_node_arr_xapp_t global_nodes;
static int const RC_ran_function = 3;

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

static rc_ctrl_req_data_t gen_rc_ctrl_msg(ran_func_def_ctrl_t const* ran_func) {
    rc_ctrl_req_data_t rc_ctrl = {0};
    rc_ctrl.hdr.format = ran_func->seq_ctrl_style[0].hdr;
    rc_ctrl.hdr.frmt_1.ric_style_type = 1;
    rc_ctrl.hdr.frmt_1.ctrl_act_id = QoS_flow_mapping_configuration_7_6_2_1;
    
    // Hard-code UE ID using struct access
    rc_ctrl.hdr.frmt_1.ue_id.type = GNB_UE_ID_E2SM;
    rc_ctrl.hdr.frmt_1.ue_id.gnb.amf_ue_ngap_id = 1; 
    
    rc_ctrl.msg.format = ran_func->seq_ctrl_style[0].msg;
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
            printf("\n[PROOF 3] ZMQ Received Command from Python: %s\n", buffer);
            lock_guard(&mtx);
            for (size_t i = 0; i < global_nodes.len; ++i) {
                e2_node_connected_xapp_t* n = &global_nodes.n[i];
                for (size_t j = 0; j < n->len_rf; j++) {
                    if (n->rf[j].id == RC_ran_function && n->rf[j].defn.rc.ctrl != NULL) {
                        printf("[PROOF 4] Sending E2SM-RC Request to Node %u...\n", n->id.nb_id.nb_id);
                        rc_ctrl_req_data_t rc_ctrl = gen_rc_ctrl_msg(n->rf[j].defn.rc.ctrl);
                        control_sm_xapp_api(&n->id, RC_ran_function, &rc_ctrl);
                        printf("[v] [PROOF 4 DONE] Control Message Dispatched!\n");
                    }
                }
            }
        }
    }
    return NULL;
}

int main(int argc, char* argv[]) {
    fr_args_t args = init_fr_args(argc, argv);
    zmq_ctx = zmq_ctx_new(); zmq_pub = zmq_socket(zmq_ctx, ZMQ_PUB); zmq_bind(zmq_pub, "tcp://*:5555");
    pthread_t control_tid; pthread_create(&control_tid, NULL, zmq_control_thread, NULL);
    init_xapp_api(&args); sleep(1);
    global_nodes = e2_nodes_xapp_api();
    pthread_mutexattr_t attr; pthread_mutexattr_init(&attr); pthread_mutex_init(&mtx, &attr);
    printf("[*] PURE CONTROL xApp started. No KPM Subscription. Waiting for Python command...\n");
    while(1) { 
        if (zmq_pub) {
            char payload[512] = "{\"meas_name\": \"DummyPRB\", \"value\": 99}";
            zmq_send(zmq_pub, payload, strlen(payload), 0);
            printf("[PROOF 1] Triggering Python Controller via ZMQ...\n");
        }
        sleep(5); 
    }
    return 0;
}
