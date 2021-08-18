import sys
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


if __name__ == "__main__":
    import getopt
    import leep

    opts, args = getopt.getopt(sys.argv[1:], 'ha:p:',
            ['help', 'addr='])
    ip_addr = '192.168.195.84'
    
    for opt, arg in opts:
        if opt in ('-h', '--help'):
            usage()
            sys.exit()
        elif opt in ('-a', '--address'):
            ip_addr = arg
    leep_addr=None 
    if leep_addr is None:
        leep_addr = "leep://" + str(ip_addr)

    leep = leep.open(leep_addr, timeout=0.1, instance=[])
    U2_adc_spi = c_llspi_ad9653(2)
    r = U2_adc_spi.read(0x00)
    w = U2_adc_spi.write(0x00, '00111100')
    print(r)
    print(w)
    U3_adc_spi = c_llspi_ad9653(3)
    r = U3_adc_spi.read(0x00)
    print(r)
