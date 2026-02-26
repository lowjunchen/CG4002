#pragma once
#include <hls_stream.h>
#include <ap_int.h>
#include "kws_hls.h"

// Define a custom AXIS struct with data and TLAST (more lightweight)
struct axis_t {
    data_t data;
    ap_uint<1> last;
};

void kws_top(hls::stream<axis_t> &s_in, hls::stream<axis_t> &s_out);