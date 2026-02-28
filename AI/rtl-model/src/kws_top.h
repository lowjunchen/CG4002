#pragma once
#include <hls_stream.h>
#include <ap_axi_sdata.h>
#include <ap_int.h>

#define AXIS_W 32

// Bit-level float to uint32 converter
typedef union {
    float f;
    unsigned int u;
} fp_conv;

typedef ap_axiu<AXIS_W, 0, 0, 0> axis_t;

void kws_top(hls::stream<axis_t> &s_in, hls::stream<axis_t> &s_out);