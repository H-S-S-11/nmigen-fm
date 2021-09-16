from nmigen import *
from nmigen.sim import *

from nco.nco_lut_pipelined import *

class FM_Mod(Elaboratable):
    def __init__(self, clk_freq=100e6, center_freq=5e6,
            bandwidth=10e3, input_shape=Shape(width=16, signed=True),
            output_shape=Shape(width=10, signed=True), prescaler=2048 ):
        
        self.input = Signal(shape=input_shape)
        self.output = Signal(shape=output_shape)

        self.phi_offset = calc_phi_inc(center_freq, clk_freq)

        # Check that prescaler and input shape and bandwidth match and < center freq
        self.prescaler_shift = int(math.log2(prescaler))
    
    def elaborate(self, platform):
        m = Module()

        offset = Const(self.phi_offset , shape=Shape(width=31, signed=False))
              
        
        m.submodules.fm_nco = fm_nco = NCO_LUT_Pipelined(output_width=self.output.width,
            sin_input_width=9, signed_output=self.output.signed)

        m.d.sync += [
            fm_nco.phi_inc_i.eq(offset + (self.input << self.prescaler_shift)),
        ]

        m.d.comb += self.output.eq(fm_nco.sine_wave_o)

        return m

if __name__=="__main__":
    dut = FM_Mod()
    sim = Simulator(dut)
    sim.add_clock(10e-9) #100MHz

    def clock():
        while True:
            yield
    
    def input():
        yield dut.input.eq(0)
        for n in range (0, 100):
            yield
        yield dut.input.eq(32000)
        for n in range (0, 100):
            yield
        yield dut.input.eq(-32000)

    sim.add_sync_process(clock)
    sim.add_sync_process(input)

    with sim.write_vcd("FM_Mod_waves.vcd"):
        sim.run_until(1e-5)