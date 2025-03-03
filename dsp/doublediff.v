`timescale 1ns / 1ns
// Differentiate when the gate is HIGH
module doublediff(
	input clk,
	input [dw-1:0] d_in, // Input data
	input g_in, // A gate when set to high differentiates input data
	output [dw-1:0] d_out,
	output g_out
);
parameter dw=28;
parameter dsr_len=4;

reg signed [dw-1:0] d1=0, d2=0;
reg valid1=0, valid2=0;
wire [dw-1:0] dpass1, dpass2;
wire svalid=g_in;

reg_delay #(.dw(dw), .len(dsr_len))
   s1(.clk(clk), .reset(1'b0), .gate(svalid), .din(d_in), .dout(dpass1));

reg_delay #(.dw(dw), .len(dsr_len))
   s2(.clk(clk), .reset(1'b0), .gate(valid1), .din(d1), .dout(dpass2));

always @(posedge clk) begin
	if (svalid) d1 <= d_in - dpass1;
	valid1 <= svalid;
	if (valid1) d2 <= d1 - dpass2;
	valid2 <= valid1;
end
assign d_out = d2;
assign g_out = valid2;
endmodule
