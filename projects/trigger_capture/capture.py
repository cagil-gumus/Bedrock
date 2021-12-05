import socket
import struct
import sys
import time

from functools import reduce

import numpy as np
from matplotlib import pyplot as plt

from litex import RemoteClient

# np.set_printoptions(threshold=sys.maxsize)

def trigger_hardware():
    wb = RemoteClient()
    wb.open()
    print(wb.regs.data_pipe_fifo_size.read())
    print(wb.regs.data_pipe_fifo_read.write(0))
    print(wb.regs.data_pipe_fifo_load.write(1))
    print(wb.regs.data_pipe_fifo_load.read())
    while wb.regs.data_pipe_fifo_full.read() != 1:
        pass

    print("Fifo full, sending read command")
    wb.regs.data_pipe_fifo_read.write(1)


def recvall(sock):
    BUFF_SIZE = 1024 * 1024 * 8 * 2   # 1M points from 8 ADCs each 2 bytes wide
    yet_to_rx = BUFF_SIZE
    data = []
    total_len = 0
    packet_cnt = 0
    sta = []
    while True:
        if yet_to_rx > 1464:
            ask = 1472
        else:
            ask = yet_to_rx + 8
        part, _ = sock.recvfrom(ask)
        data.append(part)
        total_len += len(part) - 8
        yet_to_rx -= len(part) - 8
        if total_len >= BUFF_SIZE:
            # either 0 or end of data
            break
        packet_cnt += 1

    print(f'time-rx-complete {time.time()}\npackets-received {len(data)}\nbytes-received {total_len}')
    return data

def capture(ip, port, plot_n, to_file="dump.bin"):
    # trigger_hardware()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((ip, port))
    print(sock.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF, 1024 * 1024 * 16))
    print(sock.getsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF))
    data = recvall(sock)
    ids = [struct.unpack(f'>{2}I', p[:8])[1] for p in data]

    # Checking no packets went missing
    print("checking no packets gone missing")
    for i, j in zip(ids[:-1], ids[1:]):
        if i + 1 != j:
            print(i, j)
            print("ERROR: Missing packets")

    print("splicing ..")
    D = reduce(lambda x, y: x+y, [p[8:] for p in data])
    x = len(D)//2

    print("unpacking ..")
    D = struct.unpack(f'>{x}h', D)
    D = np.array(D, np.dtype(np.int16))
    D = np.reshape(D, (-1, 8))

    print("plotting ..")
    if plot_n != 0:
        for i in range(8):
            plt.plot(D[:,i][:plot_n])
        plt.show()

    print(f"dumping to {to_file} ..")
    if to_file is not None:
        D.tofile(to_file)

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Capture buffer from zest")
    parser.add_argument("--ip", default="192.168.1.114", help="capture host ip")
    parser.add_argument("--port", default=7778, help="capture host port")
    parser.add_argument("--plot-n", default=0, help="make a plot of the first N points of all channels")
    parser.add_argument("--to-file", default="dump.bin", help="dump data to file")
    parser.add_argument("--from-file", default="", help="plot data from file; No capture in this case")
    args = parser.parse_args()
    if args.from_file != "":
        D = np.fromfile(args.from_file, dtype=np.int16)
        D = np.reshape(D, (-1, 8))
        print(D)
        print(args.plot_n)
        for i in range(8):
            plt.plot(D[:,i][:int(args.plot_n)])
        plt.show()
    else:
        capture(args.ip, args.port, args.plot_n, to_file=args.to_file)

if __name__ == "__main__":
    main()
