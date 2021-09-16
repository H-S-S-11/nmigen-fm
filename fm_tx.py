from nmigen import *
from nmigen.build import plat
from nmigen.lib.cdc import *
from nmigen.lib.io import Pin

from nco.nco_lut_pipelined import *

from fm_if import *

from nmigen_boards.ml505 import *

# Better bands might be
# 105.20-106.00,  106.00-107.00, 107.40-107.80 (numbers are stations)


class FM_TX(Elaboratable):
    def __init__(self, clk_freq=100e6, if_centre_freq=5e6, carrier=95e6,
            bandwidth=10e3):
        # 216895848 max phi inc
        # 212600881 min phi inc
        # 4294967 swing for +-10kHz
        self.clk_freq = clk_freq
        self.center_freq = if_centre_freq
        self.bandwidth = bandwidth
        self.carrier = carrier

    def elaborate(self, platform):
        m = Module()

        # Set up carrier clocks and PLL
        clk95     = Signal()
        clk95_buf = Signal()
        pll_lock  = Signal()
        clk95_fb  = Signal()
        platform.add_clock_constraint(clk95_buf, 95e6)

        m.submodules.carrier_pll = Instance("PLL_ADV",
            p_BANDWIDTH             = "OPTIMIZED",
            p_COMPENSATION          = "SYSTEM_SYNCHRONOUS",
            p_DIVCLK_DIVIDE         = 4,
            p_CLKFBOUT_MULT         = 19,
            p_CLKOUT0_DIVIDE        = 5,
            p_CLKOUT0_PHASE         = 0.00,
            p_CLKOUT0_DUTY_CYCLE    = 0.500,
            p_CLKIN1_PERIOD         = 10.000,
            i_CLKINSEL              = Const(1),
            i_CLKFBIN               = clk95_fb,
            i_RST                   = Const(0),
            o_CLKFBOUT              = clk95_fb,
            i_CLKIN1                = ClockSignal("sync"),
            o_CLKOUT0               = clk95,
            o_LOCKED                = pll_lock,
        )

        m.submodules.clk95_bufg = Instance("BUFG",
            i_I = clk95,
            o_O = clk95_buf,
        )

        # Add GPIO resources
        if(platform != None):
            platform.add_resources([
                Resource("fm_tx", 0,
                    Subsignal("carrier",      Pins("2", conn=("gpio", 0), dir="o" )),
                    Subsignal("intermediate", Pins("4", conn=("gpio", 0), dir="o" )),
                    Attrs(IOSTANDARD="LVCMOS33")
                    ),
            ])
            self.outputs = platform.request("fm_tx")
          
        m.submodules.tone = nco = NCO_LUT_Pipelined(output_width=16, 
            sin_input_width=9)

        # Input can be up to 64000 so we need to multiply by 64 to reach about 10kHz swing
        m.submodules.fm = fm = FM_Mod(prescaler=128)
        fm_wave = Signal(shape=Shape(10, True))

        m.d.comb += [
            self.outputs.carrier.o.eq(clk95_buf),
            nco.phi_inc_i.eq( calc_phi_inc(440, 100e6) ),
            fm.input.eq(nco.sine_wave_o),
            fm_wave.eq(fm.output),
            self.outputs.intermediate.o.eq(fm_wave[9]),
        ]

        return m


if __name__=="__main__":
    fm = FM_TX()
    ML505Platform().build(fm)