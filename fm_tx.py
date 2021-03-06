from nmigen import *
from nmigen.build import plat
from nmigen.lib.cdc import *
from nmigen.lib.io import Pin

from nco.nco_lut_pipelined import *

from fm_if import *

from nmigen_boards.ml505 import *

# Better bands might be
# 105.20-106.00,  106.00-107.00, 107.40-107.80 (numbers are stations)

# Can do 106.25MHz with div_in = 4, mult = 17, div_out = 4
# Can then use a 550kHz IF for 106.8 and 105.7 recieve

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
        carrier     = Signal()
        carrier_buf = Signal()
        pll_lock  = Signal()
        carrier_fb  = Signal()
        platform.add_clock_constraint(carrier_buf, 110e6)

        m.submodules.carrier_pll = Instance("PLL_ADV",
            p_BANDWIDTH             = "OPTIMIZED",
            p_COMPENSATION          = "SYSTEM_SYNCHRONOUS",
            p_DIVCLK_DIVIDE         = 4,  # 4 for 95M
            p_CLKFBOUT_MULT         = 17, # 19 for 95M
            p_CLKOUT0_DIVIDE        = 4,  # 5 for 95M
            p_CLKOUT0_PHASE         = 0.00,
            p_CLKOUT0_DUTY_CYCLE    = 0.500,
            p_CLKIN1_PERIOD         = 10.000,
            i_CLKINSEL              = Const(1),
            i_CLKFBIN               = carrier_fb,
            i_RST                   = Const(0),
            o_CLKFBOUT              = carrier_fb,
            i_CLKIN1                = ClockSignal("sync"),
            o_CLKOUT0               = carrier,
            o_LOCKED                = pll_lock,
        )

        m.submodules.carrier_bufg = Instance("BUFG",
            i_I = carrier,
            o_O = carrier_buf,
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
        # Was a bit quiet so bumped up to +- 20kHz
        m.submodules.fm = fm = FM_Mod(center_freq=550e3, prescaler=128)
        fm_wave = Signal(shape=Shape(10, True))

        m.d.comb += [
            self.outputs.carrier.o.eq(carrier_buf),
            nco.phi_inc_i.eq( calc_phi_inc(440, 100e6) ),
            fm.input.eq(nco.sine_wave_o),
            fm_wave.eq(fm.output),
            self.outputs.intermediate.o.eq(fm_wave[9]),
        ]

        return m


if __name__=="__main__":
    fm = FM_TX()
    ML505Platform().build(fm)