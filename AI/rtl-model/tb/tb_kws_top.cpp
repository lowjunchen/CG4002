#include <hls_stream.h>
#include <iostream>
#include <fstream>
#include <vector>
#include <string>
#include <cstdlib>
#include <cmath>

//Include HLS definitions
#include "kws_hls.h"
#include "kws_top.h"

//CSV Utils
static bool load_csv_floats(const std::string &path, std::vector<float> &out) {
    std::ifstream fin(path.c_str());
    if (!fin) {
        std::cerr << "ERROR: Cannot open " << path << "\n";
        return false;
    }

    out.clear();
    std::string s((std::istreambuf_iterator<char>(fin)),
                  std::istreambuf_iterator<char>());

    std::string cur;
    for (char ch : s) {
        if (ch == ',' || ch == '\n' || ch == '\r' || ch == '\t' || ch == ' ') {
            if (!cur.empty()) {
                out.push_back(std::stof(cur));
                cur.clear();
            }
        } else {
            cur.push_back(ch);
        }
    }
    if (!cur.empty()) out.push_back(std::stof(cur));
    return true;
}

int main() {
    const std::string in_path  = "tb/io/mfcc_in_0.csv";
    const std::string ref_path = "tb/io/logits_out_0.csv";

    // Load I/O data from Tensorflow
    std::vector<float> mfcc_flat;
    std::vector<float> ref_logits;

    if (!load_csv_floats(in_path, mfcc_flat)) return 1;
    if (!load_csv_floats(ref_path, ref_logits)) return 1;

    const int IN_LEN  = IN_H * IN_W;        // 98*13
    const int OUT_LEN = NUM_CLASSES;        // 7

    if ((int)mfcc_flat.size() != IN_LEN) {
        std::cerr << "ERROR: MFCC input length mismatch. Got "
                  << mfcc_flat.size() << ", expected " << IN_LEN << "\n";
        return 1;
    }
    if ((int)ref_logits.size() != OUT_LEN) {
        std::cerr << "ERROR: Ref logits length mismatch. Got "
                  << ref_logits.size() << ", expected " << OUT_LEN << "\n";
        return 1;
    }

    hls::stream<axis_t> s_in;
    hls::stream<axis_t> s_out;

    // Drive input stream in raster order: h-major then w
    for (int i = 0; i < IN_LEN; i++) { // in[h][w][0] = next stream element
        axis_t t;
        
        t.data = (data_t)mfcc_flat[i];
        t.last = (i == IN_LEN - 1) ? 1 : 0;
        
        s_in.write(t);
    }

    // Call DUT (Device Under Test) model
    kws_top(s_in, s_out);

    // Read outputs
    std::vector<float> dut_logits(OUT_LEN, 0.0f);
    
    for (int i = 0; i < OUT_LEN; i++) {
        if (s_out.empty()) {
            std::cerr << "ERROR: Output stream empty at i=" << i << "\n";
            return 1;
        }
        axis_t t = s_out.read(); // Use blocking reading
        dut_logits[i] = (float)t.data;

        // Include TLAST as additional check for data input
        if (i < OUT_LEN - 1 && t.last != 0) {
            std::cerr << "WARNING: TLAST asserted early at i=" << i << "\n";
        }
        if (i == OUT_LEN - 1 && t.last != 1) {
            std::cerr << "WARNING: TLAST not asserted on final output\n";
        }
    }

    // Compare Absolute and Relative Tolerance
    const float atol = 1e-3f;   //Absolute Tolerance
    const float rtol = 1e-3f;   //Relative Tolerance

    float max_abs_err = 0.0f;
    float max_rel_err = 0.0f;
    int fail_count = 0;

    std::cout << "Index |   Ref(logit)   |   DUT(logit)   | abs_err | rel_err\n";
    std::cout << "-----------------------------------------------------------\n";

    for (int i = 0; i < OUT_LEN; i++) {
        float ref = ref_logits[i];
        float dut = dut_logits[i];
        float abs_err = std::fabs(dut - ref);
        float denom = std::max(1e-6f, std::fabs(ref));
        float rel_err = abs_err / denom;

        if (abs_err > max_abs_err) max_abs_err = abs_err;
        if (rel_err > max_rel_err) max_rel_err = rel_err;

        bool ok = (abs_err <= atol) || (rel_err <= rtol);
        if (!ok) fail_count++;

        std::cout << "  " << i
                  << "   | " << ref
                  << " | " << dut
                  << " | " << abs_err
                  << " | " << rel_err
                  << (ok ? "" : "  <-- FAIL")
                  << "\n";
    }

    std::cout << "\nMax abs err = " << max_abs_err
              << "\nMax rel err = " << max_rel_err
              << "\nFail count  = " << fail_count << " / " << OUT_LEN << "\n";

    if (fail_count == 0) {
        std::cout << "\nPASS: HLS output matches TensorFlow golden within tolerances.\n";
        return 0;
    } else {
        std::cout << "\nFAIL: Mismatch vs TensorFlow golden.\n";
        return 2;
    }
}