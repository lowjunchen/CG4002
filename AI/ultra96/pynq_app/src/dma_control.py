import numpy as np
from pynq import allocate

def dma_transfer_axis32(dma, in_np, out_len, timeout_s=2.0, debug=False):
    """
    DMA control function to send and receive data from IP block on FPGA

    :params: 
    """
    dma.sendchannel.stop()
    dma.recvchannel.stop()
    dma.sendchannel.start()
    dma.recvchannel.start()

    in_np_u32 = np.asarray(in_np, dtype=np.uint32)

    in_buf  = allocate(shape=(in_np_u32.size,), dtype=np.uint32)
    out_buf = allocate(shape=(out_len,),        dtype=np.uint32)

    in_buf[:] = in_np_u32
    in_buf.flush()

    out_buf.invalidate() #Prepare to be written by DMA

    dma.recvchannel.transfer(out_buf)
    dma.sendchannel.transfer(in_buf)

    if debug:
        print("Transfers issued. Waiting...")

        # Timeout loop: used for debug
        import time
        t0 = time.time()
        while True:
            mm2s_sr = int(dma.mmio.read(0x04))
            s2mm_sr = int(dma.mmio.read(0x34))
            mm2s_idle = bool(mm2s_sr & (1 << 1))
            s2mm_idle = bool(s2mm_sr & (1 << 1))
            mm2s_err = bool(mm2s_sr & ((1 << 5) | (1 << 6) | (1 << 7) | (1 << 14)))
            s2mm_err = bool(s2mm_sr & ((1 << 5) | (1 << 6) | (1 << 7) | (1 << 14)))

            if mm2s_err or s2mm_err:
                if debug:
                    print("DMA error detected while waiting:")
                    dump_dma(dma)
                raise RuntimeError("DMA error during transfer")

            if mm2s_idle and s2mm_idle:
                break

            if time.time() - t0 > timeout_s:
                if debug:
                    print("TIMEOUT. DMA status:")
                    dump_dma(dma)
                raise RuntimeError("DMA timeout (likely TLAST/length mismatch or stream handshake issue)")
            time.sleep(0.005)

    dma.sendchannel.wait()
    dma.recvchannel.wait()

    out_buf.invalidate()
    out_np = np.array(out_buf, dtype=np.uint32)

    in_buf.freebuffer()
    out_buf.freebuffer()
    return out_np

def dump_dma(dma):
    '''
    DMA helper function to identify status before timeout
    '''
    mmio = getattr(dma, "mmio", getattr(dma, "_mmio", None))
    if mmio is None:
        print("Can't find dma mmio handle")
        return

    MM2S_DMASR = mmio.read(0x04)
    S2MM_DMASR = mmio.read(0x34)
    print(f"MM2S_DMASR=0x{MM2S_DMASR:08x}  S2MM_DMASR=0x{S2MM_DMASR:08x}")

    def bits(x):
        return {
            "halted":  bool(x & (1<<0)),
            "idle":    bool(x & (1<<1)),
            "int_err": bool(x & (1<<5)),
            "slv_err": bool(x & (1<<6)),
            "dec_err": bool(x & (1<<7)),
            "ioc":     bool(x & (1<<12)),
            "err_irq": bool(x & (1<<14)),
        }
    print("MM2S:", bits(MM2S_DMASR))
    print("S2MM:", bits(S2MM_DMASR))
