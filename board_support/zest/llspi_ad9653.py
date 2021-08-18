import sys
import time
from llspi import c_llspi
from ad9653 import c_ad9653


class c_llspi_ad9653(c_llspi, c_ad9653):
    def __init__(self, chip):
        self.chip = chip

    def write(self, addr, data):
        dlist = (self.ctl_bits(write=1, chipsel=self.chip, read_en=0))
        dlist += (self.data_bytes(
            self.instruction_word(
                read=0, w0w1=0, addr=addr), Nbyte=2))
        dlist += (self.data_bytes(self.data_words([eval('0b' + data)]), 1))
        dlist += (self.ctl_bits(write=1, chipsel=0))
        return dlist

    def read(self, addr):
        dlist = (self.ctl_bits(write=1, chipsel=self.chip))
        dlist += (self.data_bytes(
            self.instruction_word(
                read=1, w0w1=0, addr=addr), Nbyte=2))
        dlist += (self.ctl_bits(
            write=1, chipsel=self.chip, read_en=1, adc_sdio_dir=1))
        dlist += (self.data_bytes(self.data_words([0b01010101]), 1))
        dlist += (self.ctl_bits(write=1, chipsel=0))
        return dlist

    def usage():
        print('python %s -a [IP ADDR]' % sys.argv[0])

    def spi_write(self, obj, leep, addr, value):
        self.verbose_send(obj.write(addr, value), leep)

    def wait_for_tx_fifo_empty(self, leep):
        retries = 0
        while 1:
            rrvalue = leep.reg_read([('llspi_status')])[0]
            empty = (rrvalue >> 4) & 1
            please_read = (rrvalue + 1) & 0xf
            if empty:
                break
            time.sleep(0.002)
            retries += 1
        # print(rrvalue, type(rrvalue), hex(rrvalue), please_read)
        if retries > 0:
            print("%d retries" % retries)
        return please_read

    def verbose_send(self, dlist, leep):
        write_list = []
        [write_list.append(('llspi_we', x)) for x in dlist]
        leep.reg_write(write_list)
        time.sleep(0.002)
        return self.wait_for_tx_fifo_empty(leep)

    def U2_adc_spi_write(self, leep, addr, value):
        self.spi_write(self, leep, addr, value)


if __name__ == "__main__":
    import getopt
    import leep

    opts, args = getopt.getopt(sys.argv[1:], 'ha:p:', ['help', 'addr='])
    ip_addr = '192.168.195.84'

    for opt, arg in opts:
        if opt in ('-h', '--help'):
            sys.exit()
        elif opt in ('-a', '--address'):
            ip_addr = arg

    leep_addr = None
    if leep_addr is None:
        leep_addr = "leep://" + str(ip_addr)

    leep = leep.open(leep_addr, timeout=2.0, instance=[])
    U2_adc_spi = c_llspi_ad9653(2)
    r = U2_adc_spi.read(0x00)
    w = U2_adc_spi.write(0x00, '00111100')
    U2_adc_spi.U2_adc_spi_write(leep, 0x00, '00111100')
