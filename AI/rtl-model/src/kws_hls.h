#pragma once
#include <hls_stream.h>
#include <ap_int.h>

static const int IN_H  = 98;
static const int IN_W  = 13;
static const int IN_C  = 1;

static const int C1_COUT = 16;
static const int C2_COUT = 32;
static const int C3_COUT = 32;

static const int P1_H = 49;
static const int P1_W = 6;

static const int P2_H = 24;
static const int P2_W = 3;

// Correspond to the number of commands
static const int NUM_CLASSES = 7;

// float for exact matching with TF model
typedef float data_t;