#include "kws_layers.h"
#include "kws_top.h"

#include "conv2d_w.h"
#include "conv2d_b.h"
#include "conv2d_1_w.h"
#include "conv2d_1_b.h"
#include "conv2d_2_w.h"
#include "conv2d_2_b.h"
#include "dense_w.h"
#include "dense_b.h"

void kws_top(hls::stream<axis_t> &s_in, hls::stream<axis_t> &s_out) {
#pragma HLS INTERFACE axis port=s_in
#pragma HLS INTERFACE axis port=s_out

#pragma HLS ALLOCATION operation instances=mul limit=128 // DSP cap

    static data_t in   [IN_H][IN_W][IN_C];
    static data_t c1   [IN_H][IN_W][C1_COUT];
    static data_t p1   [P1_H][P1_W][C1_COUT];
    static data_t c2   [P1_H][P1_W][C2_COUT];
    static data_t p2   [P2_H][P2_W][C2_COUT];
    static data_t c3   [P2_H][P2_W][C3_COUT];
    static data_t gap  [C3_COUT];
    static data_t out  [NUM_CLASSES];

#pragma HLS ARRAY_PARTITION variable=gap complete
#pragma HLS ARRAY_PARTITION variable=out complete

    // Read input stream -> in[98][13][1], using float point converter
    fp_conv conv_in;
    for (int h = 0; h < IN_H; h++) {
        for (int w = 0; w < IN_W; w++) {
#pragma HLS PIPELINE II=1
            axis_t t = s_in.read();
            conv_in.u = (unsigned int)t.data;     // ap_uint<32> -> uint32 bits
            in[h][w][0] = (data_t)conv_in.f;      // float -> ap_fixed<32,12>
        }
    }

    // Conv2d layer 1 + ReLU
    conv2d_3x3_relu<IN_H, IN_W, IN_C, C1_COUT>(in, c1, conv2d_w, conv2d_b);
    
    // Pooling
    maxpool2x2_stride2<IN_H, IN_W, C1_COUT, P1_H, P1_W>(c1, p1);

    // Conv2d layer 2 + ReLU
    conv2d_3x3_relu<P1_H, P1_W, C1_COUT, C2_COUT>(p1, c2, conv2d_1_w, conv2d_1_b);
    
    // Pooling
    maxpool2x2_stride2<P1_H, P1_W, C2_COUT, P2_H, P2_W>(c2, p2);

    // Conv2d layer 3 + ReLU
    conv2d_3x3_relu<P2_H, P2_W, C2_COUT, C3_COUT>(p2, c3, conv2d_2_w, conv2d_2_b);

    // Global Average Pooling
    global_avg_pool<P2_H, P2_W, C3_COUT>(c3, gap);

    // Dense -> No. of Classes (7) logits
    dense<C3_COUT, NUM_CLASSES>(gap, out, dense_w, dense_b);

    // Write logits
    fp_conv conv_out;
    for (int i = 0; i < NUM_CLASSES; i++) {
#pragma HLS PIPELINE II=1
        axis_t t;

        conv_out.f = (float)out[i];           // ap_fixed -> float (numeric)
        t.data = (ap_uint<32>)conv_out.u;     // float bits -> AXIS payload

        t.last = (i == NUM_CLASSES - 1) ? 1 : 0;

        s_out.write(t);
    }
}