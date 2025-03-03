`timescale 1ns / 1ns

/* CIC Wave Recorder
   Generic waveform recording system comprised of:
   - Multichannel CIC filter with runtime selectable base sample rate and waveform
     sampling rate (cc_samp_per)
   - Double-buffered circular buffer that can be read through a local bus interface

         +------------------------+
         |  +-------+    +------+ |
 in[0]+----->       |    |      <---+ rd_addr/stb
         |  |  CIC  |    | CIRC | |
 in[1]+----->       +----> BUF  | |
         |  |MULTICH|    |SERIAL+---> d_out
 in[N]+----->       |    |      | |
         |  +---^---+    +---^--+ |
         |      |            |    |
         +------------------------+
                |            |
     cic_sample +            + cc_sample
*/

module cic_wave_recorder #(
   parameter n_chan=12,

   // DI parameters
   parameter di_dwi=16,       // data width
   parameter di_rwi=32,       // result width
                              // Difference between above two widths should be N*log2 of the maximum number
                              // of samples per CIC sample, where N=2 is the order of the CIC filter.
   parameter di_noise_bits=4, // Number of noise bits to discard at the output of Double Integrator.
                              // This depends on the SNR of the inputs and the CIC sample rate
   // CCFILT parameters
   parameter cc_outw=20,      // CCFilt output width; Must be 20 if using half-band filter
   parameter cc_halfband=1,
   parameter cc_use_delay=0,  // Match pipeline length of filt_halfband=1
   parameter cc_shift_base=0, // Bits to discard from previous acc step
   parameter cc_shift_wi=4,


   // Circular Buffer parameters
   parameter buf_dw=16,       // If buf_dw < cc_outw, lsb are dropped
                              // If buf_dw > cc_outw, msbs are zero-filled
   parameter buf_aw=13,
   parameter lsb_mask=1,      // LSB of channel mask is CH0
   parameter buf_stat_w=16,
   parameter buf_auto_flip=1) // auto_flip=1: Double buffers will be flipped when
                              //              last read address is reached
                              // auto_flip=0: Buffers must be explicitly flipped by
                              //              using stb_out as a pulse and not a strobe
(
   input                      iclk,
   input                      reset,
   input                      stb_in,          // Strobe signal for input samples
   input [n_chan*di_dwi-1:0]  d_in,            // Flattened array of unprocessed data streams. CH0 in LSBs
   input                      cic_sample,      // CIC base sampling signal

   // Post-integrator conveyor belt tap
   output                      di_stb_out,
   output [di_rwi-1:0]         di_sr_out,

   // CC Filter controls
   input                      cc_sample,       // CCFilt sampling signal
   input [cc_shift_wi-1:0]    cc_shift,        // controls scaling of filter result

   // Channel selector controls
   input [n_chan-1:0]         chan_mask,       // Bitmask of channels to record

   // Selected waveform data in iclk domain
   output                     wave_gate_out,
   output                     wave_dval_out,
   output                     [buf_dw-1:0] wave_data_out,

   // Circular Buffer control and status
   input                      oclk,
   input                      buf_write,       // Level-signal to enable writing into buffer
   output                     buf_sync,        // single-cycle when buffer starts/ends
   output                     buf_transferred, // single-cycle when a buffer has been
                                               // handed over for reading;
                                               // one cycle delayed from buf_sync
   input                      buf_stop,        // single-cycle - interrupts cbuf writing
   output [buf_stat_w-1:0]    buf_count,
   output [buf_aw-1:0]        buf_stat2,       // includes fault bit
   output [buf_stat_w-1:0]    buf_stat,        // includes fault bit, and (if set) the last valid location
   output [buf_aw+4:0]        debug_stat,      // {stb_in, boundary, btest, wbank, rbank, wr_addr}

   // Circular Buffer data readout
   input                      buf_stb,
   output                     buf_enable,
   input  [buf_aw-1:0]        buf_read_addr,   // nominally 8192 locations
   output [buf_dw-1:0]        buf_d_out
);

   // ------
   // CIC Filter
   // ------
   wire cic_stb_out;
   wire [cc_outw-1:0] cic_sr_out;

   cic_multichannel #(
      .n_chan        (n_chan),
      .di_dwi        (di_dwi),
      .di_rwi        (di_rwi),
      .di_noise_bits (di_noise_bits),
      .cc_outw       (cc_outw),
      .cc_halfband   (cc_halfband),
      .cc_use_delay  (cc_use_delay),
      .cc_shift_base (cc_shift_base),
      .cc_shift_wi   (cc_shift_wi))
   i_cic_multichannel
   (
      .clk           (iclk),
      .reset         (reset),
      .stb_in        (stb_in),
      .d_in          (d_in),
      .cic_sample    (cic_sample),

      .cc_sample     (cc_sample),
      .cc_shift      (cc_shift),

      .di_stb_out    (di_stb_out),
      .di_sr_out     (di_sr_out),

      .cc_stb_out    (cic_stb_out),
      .cc_sr_out     (cic_sr_out)
   );

   // ------
   // Double-buffered circular buffer
   // ------

   wire [buf_dw-1:0] wave_data_i;

   // Resize output of CIC filter so it can be stored in circle_buf
   generate
      if (cc_outw > buf_dw) begin: g_wave_data_resize
         assign wave_data_i = cic_sr_out[cc_outw-1:(cc_outw-buf_dw)]; // Drop lsbs
      end else if (cc_outw < buf_dw) begin
         assign wave_data_i = {{(buf_dw-cc_outw){1'b0}}, cic_sr_out}; // Zero extend
      end else begin
         assign wave_data_i = cic_sr_out;
      end
   endgenerate

   // Avoid partial strobes/bursts when using buf_write
   // Assume strobes are well formed (asserted in fchan_subset)
   // Count beats in case there's no separation between bursts
   reg [4:0] chan_stb_cnt=0;
   reg wr_gated_r=0;

   wire wr_gated = (chan_stb_cnt==0 && !buf_write);

   always @(posedge iclk) begin
      if (cic_stb_out) begin
         chan_stb_cnt <= chan_stb_cnt + 1;

         if (wr_gated) wr_gated_r <= 1;
      end

      if (chan_stb_cnt == n_chan-1) begin
         chan_stb_cnt <= 0;
         wr_gated_r <= 0;
      end
   end

   circle_buf_serial #(
      .n_chan        (n_chan),
      .lsb_mask      (lsb_mask),
      .buf_aw        (buf_aw),
      .buf_dw        (buf_dw),
      .buf_stat_w    (buf_stat_w),
      .buf_auto_flip (buf_auto_flip))
   i_circle_buf_serial (
      .iclk            (iclk),
      .reset           (reset),
      .sr_in           (wave_data_i),
      .sr_stb          (cic_stb_out & (~wr_gated & ~wr_gated_r)),
      .chan_mask       (chan_mask),
      .wave_data       (wave_data_out),
      .wave_dval       (wave_dval_out),
      .wave_gate       (wave_gate_out),
      .oclk            (oclk),
      .buf_sync        (buf_sync),
      .buf_transferred (buf_transferred),
      .buf_stop        (buf_stop),
      .buf_count       (buf_count),
      .buf_stat2       (buf_stat2),
      .buf_stat        (buf_stat),
      .debug_stat      (debug_stat),
      .stb_out         (buf_stb),
      .enable          (buf_enable),
      .read_addr       (buf_read_addr),
      .d_out           (buf_d_out)
   );

endmodule

