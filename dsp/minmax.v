`timescale 1ns / 1ns

// Simple always-on minmax finder, designed to be applied to ADC inputs.
// reset is single-cycle, designed such that you can capture the outputs
// on the same cycle as you apply the reset, resulting in no blind cycles.
module minmax(clk,xin,reset,xmin,xmax);
parameter width=14;

	input clk;
	input signed [width-1:0] xin;
	input reset;
	output signed [width-1:0] xmin;
	output signed [width-1:0] xmax;
reg signed [width-1:0] xin_d=0;
reg signed [width-1:0] xmin_r={width{1'b1}};
reg signed [width-1:0] xmax_r={width{1'b0}};
wire signed [width-1:0] max_plus = {1'b0,{(width-1){1'b1}}};
always @ (posedge clk) begin
	xin_d<=xin;
	xmax_r <= reset ? (xin_d) : (xin_d>xmax_r) ? xin_d : xmax_r;
	xmin_r <= reset ? (xin_d) : (xin_d<xmin_r) ? xin_d : xmin_r;
	//xmax_r <= reset ? (~max_plus) : (xin>xmax_r) ? xin : xmax_r;
	//xmin_r <= reset ? ( max_plus) : (xin<xmin_r) ? xin : xmin_r;
end
assign xmax = xmax_r;
assign xmin = xmin_r;

endmodule
