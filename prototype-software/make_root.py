import ROOT
import sys

import numpy as np
import struct
from array import array

from qdb_interface import PACKET_HEADER, EXIT_PACKET

def main():
    """
    only run this as a script
    """

    # create ROOT file
    tf = ROOT.TFile("new_root.root", "RECREATE")
    tt = ROOT.TTree("tt", "dataTree")

    timestamp = array('I', [0])
    chmask = array('H', [0])
    meta = array('H', [0])
    pid = array('H', [0])

    tt.Branch("Timestamp", timestamp, "timestamp/I")
    tt.Branch("ChMask", chmask, "chan/s")
    tt.Branch("Meta", meta, "meta/s")
    tt.Branch("pid", pid, "pid/s")
    hddr_size = len(PACKET_HEADER)

    # open binary file
    with open("saqTmp.bin", "rb") as f:
        data = f.read()

    i = 0
    while i < len(data):
        hddr = data[i:hddr_size+i]
        i += hddr_size

        found = hddr==PACKET_HEADER
        if not found:
            print("WARNING unable to find packet hddr:", hddr)
            break
        size = struct.unpack("I", data[i:i+4])[0]
        i += 4
        pid[0] = struct.unpack("<H", data[i+size-2:i+size])[0]

        words = int(size/8)
        for j in range(words):
            timestamp[0] = struct.unpack("<I", data[i:i+4])[0]
            i += 4
            chmask[0] = struct.unpack("<H", data[i:i+2])[0]
            i += 2
            meta[0] = struct.unpack("<H", data[i:i+2])[0]
            i += 2
            tt.Fill()
        # packet_id
        i += 2

    tf.Write()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        print("ERROR should only run by default")
    else:
        main()