'''
top-level multichannel plotter.
Revamp with kivy started
TODO:
1. Move MeshLinePlot into a Kivy Graph object
2. Verify the performance of gather data and plot (for now different threads)
'''
import sys
import time
from threading import Thread

import numpy as np
from matplotlib import pyplot as plt

from banyan_ch_find import banyan_ch_find
from banyan_spurs import collect_adcs
from prc import c_prc


def write_mask(prc, mask_int):
    prc.reg_write([{'banyan_mask': mask_int}])
    channels = banyan_ch_find(mask_int)
    n_channels = len(channels)
    print((channels, 8 / n_channels))
    return n_channels, channels


def get_npt(prc):
    banyan_status = prc.reg_read_value(['banyan_status'])[0]
    npt = 1 << ((banyan_status >> 24) & 0x3F)
    if npt == 1:
        print("aborting since hardware module not present")
        sys.exit(2)
    return npt


class ADC:
    bits = 16
    scale = 1 << (bits - 1)  # signed
    sample_rate = 100000000.
    count_to_1volt = 1. / scale
    # 6dbm = 10 * log10(P/1e-3W)
    # 10 ** (6 / 10) = P / 1e-3
    # 10 ** (0.6) * 1e-3 = P
    # Assuming P = V**2 / 50 Ohms
    # V**2 = 1e-3 * (10 ** 0.6) * 50
    # V = np.sqrt(1e-3 * (10 ** 0.6) * 50)
    dbm_to_Vrms = np.sqrt(1e-3 * (10 ** 0.6) * 50)
    Vzp = dbm_to_Vrms * np.sqrt(2)

    def counts_to_volts(raw_counts):
        # TODO: This should be adjusted to ADC.Vzp and verified
        return raw_counts * ADC.count_to_1volt


class Carrier:
    def __init__(self,
                 ip_addr='192.168.1.121',
                 port=50006,
                 mask="0xff",
                 npt_wish=0,
                 count=10,
                 verbose=False,
                 filewritepath=None,
                 use_spartan=False,
                 test=False):
        if not test:
            self.carrier = c_prc(ip_addr, port, filewritepath=filewritepath,
                                 use_spartan=use_spartan)

            self.npt = get_npt(self.carrier)
            mask_int = int(mask, 0)
            self.n_channels, channels = write_mask(self.carrier, mask_int)
        else:
            banyan_aw = 13
            self.npt = 2 ** banyan_aw
            self.n_channels = 2

        self.pts_per_ch = self.npt * 8 // self.n_channels
        self.test_counter = 0

    def test_data(self, *args):
        while True:
            self.test_counter += 1
            self.nblock = np.array([np.random.random_sample(self.pts_per_ch)
                                    for _ in range(self.n_channels)])
            time.sleep(0.2)

    def acquire_data(self, *args):
        # collect_adcs is not normal:
        # It always collects npt * 8 data points.
        # Each channel gets [(npt * 8) // n_channels] datapoints
        data_block, self.ts = collect_adcs(self.carrier, self.npt, self.n_channels)
        # ADC count / FULL SCALE => [-1.0, 1.        pass
        self.nblock = ADC.counts_to_volts(np.array(data_block))


g_channels = []


# TODO: Should convert this to a dataclass for python 3.7+
class GUIGraphChannel:
    def __init__(self, ch_id, show_freq=False, show_ts=False, xlog=False, ylog=False):
        self.ch_id = ch_id
        self.show_freq = show_freq
        self.show_ts = show_ts
        self.xlog = False
        self.ylog = False

    @staticmethod
    def setup_gui_channels(carrier):
        for i in range(carrier.n_channels):
            g_channels.append(GUIGraphChannel("0"+str(i), False, False, False, False))
            g_channels.append(GUIGraphChannel("1"+str(i), False, False, False, False))
        g_channels.append(GUIGraphChannel("3", False, False, False, False))


from kivy.lang import Builder
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.clock import Clock
from kivy.garden.matplotlib.backend_kivyagg import FigureCanvas
from kivy.logger import Logger


default_ts_kwargs = {'ylabel': 'volts',
                     'xlabel': 'sample_number',
                     'label': 'Time Series'}


class Logic(BoxLayout):
    def __init__(self, **kwargs):
        super(Logic, self).__init__()
        self.setup_channels(carrier.n_channels)

    def setup_channel(self, i):
        fig = plt.figure()
        wid = FigureCanvas(fig)
        self.widgets.append(wid)
        ax = fig.add_subplot(111)
        ax.axis(**default_ts_kwargs)
        self.axes.append(ax)

    def setup_channels(self, n_channels):
        self.axes, self.widgets = [], []
        for i in range(len(g_channels)):
            self.setup_channel(g_channels[i])
        Logger.info("added axes")

    def ch_select(self, *args):
        plot_type = int(args[0][0])
        if plot_type < 2:
            ch_number = int(args[0][1])
            gui_plot_index = 2 * ch_number + plot_type
        else:
            gui_plot_index = 2 * carrier.n_channels

        if args[-1]:
            self.add_widget(self.widgets[gui_plot_index])
        else:
            self.remove_widget(self.widgets[gui_plot_index])

    def start(self):
        Clock.schedule_interval(self.get_value, 0.01)

    def stop(self):
        Clock.unschedule(self.get_value)

    def get_value(self, dt):
        self.plot.set_xdata(range(len(carrier.nblock[0])))
        self.plot.set_ydata(carrier.nblock[0])
        self.wid.draw()
        self.ax.relim()
        self.ax.autoscale()


class Oscope(App):
    def build(self):
        return Builder.load_file("look.kv")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Read/Write from FPGA memory')
    parser.add_argument(
        '-a',
        '--ip',
        help='ip_address',
        dest='ip',
        type=str,
        default='192.168.1.121')
    parser.add_argument(
        '-p', '--port', help='port', dest='port', type=int, default=50006)
    parser.add_argument(
        '-m', '--mask', help='mask', dest='mask', type=str, default='0x3')
    parser.add_argument(
        '-n',
        '--npt_wish',
        help='number of points per channel',
        type=int,
        default=4096)
    parser.add_argument(
        '-c', '--count', help='number of acquisitions', type=int, default=1)
    parser.add_argument(
        '-f', '--filewritepath', help='static file out', type=str, default="")
    parser.add_argument(
        "-u",
        "--use_spartan",
        action="store_true",
        help="use spartan",
        default=True)
    args = parser.parse_args()
    carrier = Carrier(ip_addr=args.ip,
                      port=args.port,
                      mask=args.mask,
                      npt_wish=args.npt_wish,
                      count=args.count,
                      filewritepath=args.filewritepath,
                      use_spartan=args.use_spartan,
                      test=True)
    GUIGraphChannel.setup_gui_channels(carrier)
    acq_thread = Thread(target=carrier.test_data)
    acq_thread.daemon = True
    acq_thread.start()
    Oscope().run()
