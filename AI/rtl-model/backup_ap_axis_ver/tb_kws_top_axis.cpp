#include <hls_stream.h>
#include <iostream>
#include <fstream>
#include <vector>
#include <string>
#include <cstdlib>
#include <cmath>
#include <algorithm>

#include "kws_hls.h"
#include "kws_top.h"

// -----------------------------
// CSV Utils
// -----------------------------
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

    // Load I/O data
    std::vector<float> mfcc_flat;
    std::vector<float> ref_logits;
    if (!load_csv_floats(in_path, mfcc_flat)) return 1;
    if (!load_csv_floats(ref_path, ref_logits)) return 1;

    const int IN_LEN  = IN_H * IN_W;
    const int OUT_LEN = NUM_CLASSES;

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

    // -----------------------------
    // Push input samples (simple style)
    // -----------------------------
    // NOTE: Your DUT does not use input TLAST. Keep it 0 to avoid framing assumptions.
    // (If you want to mark frame end anyway, set last on final sample.)
    fp_conv pack;
    for (int i = 0; i < IN_LEN; i++) {
        axis_t t;
        
        pack.f  = mfcc_flat[i];                 // float value
        t.data  = (ap_uint<32>)pack.u;          // float32 bits -> AXIS payload
        
        t.last = 0;                             // ignore input TLAST
        
        s_in.write(t);
    }

    // -----------------------------
    // Call DUT
    // -----------------------------
    kws_top(s_in, s_out);

    // -----------------------------
    // Read exactly OUT_LEN outputs (mimic proven working example)
    // -----------------------------
    std::vector<float> dut_logits(OUT_LEN, 0.0f);

    bool saw_last = false;
    fp_conv unpack;
    
    for (int i = 0; i < OUT_LEN; i++) {
        axis_t t = s_out.read();          // blocking read
        
        unpack.u = (unsigned int)t.data;
        dut_logits[i] = unpack.f;
        
        // Use output TLAST as additional check for end of data
        if (t.last) {
            if (i != OUT_LEN - 1) {
                std::cerr << "WARNING: TLAST asserted early at output i=" << i << "\n";
            }
            saw_last = true;
        }
    }

    if (!saw_last) {
        std::cerr << "WARNING: TLAST was never observed in the first "
                  << OUT_LEN << " outputs.\n";
    }

    // -----------------------------
    // Compare against reference
    // -----------------------------
    const float atol = 1e-3f;
    const float rtol = 1e-3f;

    float max_abs_err = 0.0f;
    float max_rel_err = 0.0f;
    int fail_count = 0;

    // Output result table heading
    std::cout << "Index |   Ref(logit)   |   DUT(logit)   | abs_err | rel_err\n";
    std::cout << "-----------------------------------------------------------\n";

    for (int i = 0; i < OUT_LEN; i++) {
        float ref = ref_logits[i];
        float dut = dut_logits[i];

        float abs_err = std::fabs(dut - ref);
        float denom = std::max(1e-6f, std::fabs(ref));
        float rel_err = abs_err / denom;

        max_abs_err = std::max(max_abs_err, abs_err);
        max_rel_err = std::max(max_rel_err, rel_err);

        bool ok = (abs_err <= atol) || (rel_err <= rtol);
        if (!ok) fail_count++;

        // Output result table row
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