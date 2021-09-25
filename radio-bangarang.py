from nmigen import *
from nmigen.build import plat
from nmigen.lib.cdc import *
from nmigen.lib.io import Pin

from nco.nco_lut_pipelined import *
from nco.fir_pipelined import FIR_Pipelined
from nco.pdm import PDM
from peripherals.ac97 import AC97_Controller
from fm_if import *

from utility.uart_rx import UART_RX

from nmigen_boards.ml505 import *

# Better bands might be
# 105.20-106.00,  106.00-107.00, 107.40-107.80 (numbers are stations)

# Can do 106.25MHz with div_in = 4, mult = 17, div_out = 4
# Can then use a 550kHz IF for 106.8 and 105.7 recieve

class Radio_Bangarang(Elaboratable):
    def __init__(self, audio_resolution=8, clk_freq=100e6, if_centre_freq=5e6, carrier=95e6,
            bandwidth=10e3):
        # 216895848 max phi inc
        # 212600881 min phi inc
        # 4294967 swing for +-10kHz
        self.clk_freq = clk_freq
        self.center_freq = if_centre_freq
        self.bandwidth = bandwidth
        self.carrier = carrier

        self.audio_resolution = audio_resolution

    def elaborate(self, platform):
        m = Module()

        speedup = 2

        # UART loopback
        m.submodules.uart_rx = uart_rx = UART_RX(baud_rate=speedup*441000, fclk=100e6)
        
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
                Resource("uart", 0,
                    Subsignal("rx", Pins("26", conn=("gpio", 0) ,dir="i")),
                    Subsignal("tx", Pins("28", conn=("gpio", 0) ,dir="o")),
                ),
            ])
            self.outputs = platform.request("fm_tx")
            uart    = platform.request("uart")
            dpad = platform.request("dpad")
          
        m.submodules.tone = nco = NCO_LUT_Pipelined(output_width=16, 
            sin_input_width=9)
        m.submodules.lpf = lpf = FIR_Pipelined(taps=16, cutoff=15e3/100e6)
        m.submodules.pdm= pdm = PDM(resolution = self.audio_resolution )

        # Input can be up to 64000 so we need to multiply by 64 to reach about 10kHz swing
        # Was a bit quiet so bumped up to +- 20kHz
        m.submodules.fm = fm = FM_Mod(center_freq=550e3, prescaler=256)
        fm_wave = Signal(shape=Shape(10, True))

        old_valid = Signal()
        data_buff = Signal(8)
        phi_inc = Signal(32)
        with m.Switch(data_buff):
            with m.Case(65):
                m.d.comb += phi_inc.eq( calc_phi_inc(440, 100e6) )
            with m.Case(66):
                m.d.comb += phi_inc.eq( calc_phi_inc(493.88, 100e6) )
            with m.Case(67):
                m.d.comb += phi_inc.eq( calc_phi_inc(523.25, 100e6) )
            with m.Case(68):
                m.d.comb += phi_inc.eq( calc_phi_inc(587.33, 100e6) )
            with m.Case(69):
                m.d.comb += phi_inc.eq( calc_phi_inc(659.25, 100e6) )
            with m.Case(70):
                m.d.comb += phi_inc.eq( calc_phi_inc(698.46, 100e6) )
            with m.Case(71):
                m.d.comb += phi_inc.eq( calc_phi_inc(783.99, 100e6) )
            with m.Default():
                m.d.comb += phi_inc.eq( calc_phi_inc(440, 100e6) )

        m.d.sync += old_valid.eq(uart_rx.valid)

        with m.If( uart_rx.valid & ~old_valid ):
            m.d.sync += data_buff.eq(uart_rx.data)

        m.d.comb += [
            self.outputs.carrier.o.eq(carrier_buf),
            nco.phi_inc_i.eq( phi_inc ),

            lpf.input.eq( data_buff << 8 ),
            lpf.input_ready_i.eq(Const(1)),    
            # fm.input.eq(nco.sine_wave_o),
            fm.input.eq( data_buff << 8 ),
            
            fm_wave.eq(fm.output),
            self.outputs.intermediate.o.eq(fm_wave[9]),

            uart_rx.rx.eq(uart.rx.i),

            pdm.input.eq(data_buff),
            pdm.write_en.eq(0),
        ]

        return m


if __name__=="__main__":
    fm = Radio_Bangarang()
    ML505Platform().build(fm)