#pragma once
#include "kws_hls.h"

inline int idx4_conv_w(int kh, int kw, int cin, int cout, int Cin, int Cout) {
    return (((kh*3 + kw)*Cin + cin)*Cout + cout);
}

inline int idx2_dense_w(int in, int out, int Out) {
    return in*Out + out;
}

// Implement convolution with 3x3 kernel, SAME padding, stride 1 + RELU
template<int H, int W, int Cin, int Cout>
void conv2d_3x3_relu(
    const data_t in[H][W][Cin],
    data_t out[H][W][Cout],
    const data_t w[3*3*Cin*Cout],
    const data_t b[Cout]
) {
#pragma HLS INLINE off

    for (int oh = 0; oh < H; oh++) {
        for (int ow = 0; ow < W; ow++) {
            for (int co = 0; co < Cout; co++) {
                acc_t acc = (acc_t)b[co];

                for (int kh = 0; kh < 3; kh++) {
                    for (int kw = 0; kw < 3; kw++) {
                        int ih = oh + kh - 1;
                        int iw = ow + kw - 1;

                        if (ih >= 0 && ih < H && iw >= 0 && iw < W) {
                            for (int ci = 0; ci < Cin; ci++) {
#pragma HLS PIPELINE II=1
                                data_t x  = in[ih][iw][ci];
                                data_t ww = w[idx4_conv_w(kh, kw, ci, co, Cin, Cout)];
                                acc += (acc_t)x * (acc_t)ww;
                            }
                        }
                    }
                }

                // RELU activation
                data_t y = (data_t)acc;
                out[oh][ow][co] = (y > (data_t)0) ? y : (data_t)0;
            }
        }
    }
}

// Implement max pooling with 2x2 kernel, stride 2, no padding
template<int H, int W, int C, int OH, int OW>
void maxpool2x2_stride2(
    const data_t in[H][W][C],
    data_t out[OH][OW][C]
) {
#pragma HLS INLINE off
    for (int h = 0; h < OH; h++) {
        for (int w = 0; w < OW; w++) {
            for (int c = 0; c < C; c++) {
#pragma HLS PIPELINE II=1
                int ih = h * 2;
                int iw = w * 2;
                data_t m = in[ih][iw][c];
                data_t v1 = in[ih][iw+1][c];
                data_t v2 = in[ih+1][iw][c];
                data_t v3 = in[ih+1][iw+1][c];
                if (v1 > m) m = v1;
                if (v2 > m) m = v2;
                if (v3 > m) m = v3;
                out[h][w][c] = m;
            }
        }
    }
}

// Implement global average pooling
template<int H, int W, int C>
void global_avg_pool(const data_t in[H][W][C], data_t out[C]) {
#pragma HLS INLINE off
    const data_t inv = (data_t)1 / (data_t)(H*W);

    for (int c = 0; c < C; c++) {
        acc_t acc = 0;
        for (int h = 0; h < H; h++) {
            for (int w = 0; w < W; w++) {
                acc += in[h][w][c];
            }
        }
        out[c] = (data_t) (acc * inv);
    }
}

// Implement fully connected layer (dense layer)
template<int In, int Out>
void dense(
    const data_t in[In],
    data_t out[Out],
    const data_t w[In*Out],
    const data_t b[Out]
) {
#pragma HLS INLINE off
    for (int o = 0; o < Out; o++) {
#pragma HLS PIPELINE II=1
        acc_t acc = b[o];
        for (int i = 0; i < In; i++) {
            acc += in[i] * w[idx2_dense_w(i, o, Out)];
        }
        out[o] = (data_t) acc; // output logits
    }
}