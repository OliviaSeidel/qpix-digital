#!/usr/bin/env python3

import os
import sys
import ROOT
import numpy

from SAQ_DAQ import N_SAQ_CHANNELS

def main(input_file, use_multithread=True):
    """
    Test script for running a simple analysis on ROOT files generated from
    qdb_interface based GUIs like SAQ_DAQ.py

    Supply input file to read, then this script should be able to parse that
    data and supply desired graphics
    """
    if use_multithread:
        ROOT.EnableImplicitMT() # gotta go fast

    # open up ttree into an rdataframe, which is easy to convert to a list
    rdf = ROOT.RDataFrame("tt", input_file)

    # rip everything immediately into a dictionary, where the keys are
    # the branch names
    data = rdf.AsNumpy()

    # numpy arrays of the data we need
    ts = data["Timestamp"]
    masks = data["ChMask"]

    # make a quick way to ensure the channel we want is in the mask
    m = lambda ch, mask: 1 << ch & mask

    # create a list of the channels and all of their resets
    chResets = [[t for t, mask in zip(ts, masks) if m(ch, mask)] for ch in range(N_SAQ_CHANNELS)]

    # inspect the resets to ensure they make sense
    for ch, resets in enumerate(chResets):
        print(f"ch: {ch+1} has {len(resets)} resets.")

    # chTDRs is a list of a list where the first index is the channel number -1
    # (lists are zero counted), which contain the sequential time since last
    # reset data
    chTDRs = [[r[i+1] - r[i] for i in range(len(r[:-1]))] for r in chResets]

    ###################################
    # extra analysis can proceed here #
    ###################################


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("ERROR user must supply input file name")
    else:
        input_file = sys.argv[1]
        if not os.path.isfile(input_file) or os.path.getsize(input_file) == 0:
            print("empty or non-existent input ROOT file", input_file)
            sys.exit(-1)
        main(input_file)
