#pragma once
#include <hls_stream.h>
#include <ap_int.h>
#include <ap_fixed.h>

constexpr int IN_H  = 98;
constexpr int IN_W  = 13;
constexpr int IN_C  = 1;

constexpr int C1_COUT = 16;
constexpr int C2_COUT = 32;
constexpr int C3_COUT = 32;

constexpr int P1_H = 49;
constexpr int P1_W = 6;

constexpr int P2_H = 24;
constexpr int P2_W = 3;

// Correspond to the number of commands
constexpr int NUM_CLASSES = 7;

// Fixed-point datatype for CNN data
typedef ap_fixed<32,12> data_t;

// Accmulator for conv/dense
typedef ap_fixed<48,20> acc_t;