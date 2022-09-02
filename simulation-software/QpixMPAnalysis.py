import multiprocessing as mp
import numpy as np
import QpixAsicArray as qparray
from QpixAsicArray import PrintTransactMap
from QpixAsic import QPFifo
import pandas as pd

## This Script reads in the output of radiogenicNB.ipynb (which reads in output from radiogenic ROOT data)
## and then executes a parameter space search utilizing multiprocessing to speed things up

MAXTIME = 10 # time to integrate for, or time radiogenic data is based on

def runTile(queue, tile, int_prd, int_time=MAXTIME):
    """
    basic function to run a tile with an integration period, over a specified time

    store processed tile on output queue to send back to main thread.
    """
    # interrogation sequence
    int_period = np.linspace(0, int_time, int(int_time/int_prd))

    for i in int_period:
        tile.Interrogate(int_prd)

    queue.put(tile)


def main(seed=2):
    """
    This script should be called and run as an executable.
    """

    # set up the input data / tile information
    inFile = "tiledf05.json"

    # import the radiogenic hit data
    import codecs, json
    obj_text = codecs.open(inFile, 'r').read()
    readDF = json.loads(obj_text)
    nrows = readDF["nrows"]
    ncols = readDF["ncols"]
    ncpu = mp.cpu_count() - 1

    # define the ranges of parameters to test
    int_periods = np.linspace(0.1,1,10)
    routes = ["left", "snake"]
    timeouts = [15e3, 30e3, 15e4, 30e4, 15e5, 30e5]

    # create the list of tiles to send to the multi-proc analysis
    maxTime = 10 # seconds for how long to integrate till
    tiles = [] 
    int_prd = []
    for r in routes:
        for i in int_periods:
            for t in timeouts:
                # re-seed?
                tile = qparray.QpixAsicArray(nrows, ncols, tiledf=readDF, timeout=t)
                tile.Route(r, transact=False)
                tiles.append(tile)
                int_prd.append(i)

    # place holder for the completed tiles
    tile_queue = mp.Queue()

    # create a list of all of the processes that need to run.
    procs = [mp.Process(target=runTile, args=(tile_queue, tile, time)) for (tile, time) in zip(tiles, int_prd)]
    completeProcs = 0
    runningProcs = []
    nProcs = len(procs)

    print(f"begginning processing of {nProcs} tiles.")

    pTiles = []
    while completeProcs < nProcs:

        # fill running procs until we use all cpu threads
        while len(runningProcs) < ncpu and len(procs) > 0:
            runningProcs.append(procs.pop())

        # ensure all of the running procs have started
        for ip, p in enumerate(runningProcs):
            if p.pid is None:
                p.start()
            elif p.exitcode is not None:
                runningProcs.pop(ip)

        # wait to get anything on the queue
        pTiles.append(tile_queue.get())
        completeProcs = len(pTiles)
        print(f"Completed tile {completeProcs}, {completeProcs/nProcs*100:0.2f}%..")


    tiles = pTiles
    data = {
        "Architecture":[tile.push_state for tile in tiles for asic in tile],
        "Route":[tile.RouteState for tile in tiles for asic in tile],
        # different architectures use different parameters
        # a pull architecture requires (integration frequency, timeout)
        # a push architecture requires (wait time?)
        "Params":[(args[0], tile[0][0].config.timeout) if not tile.push_state else args for (tile, *args) in zip(tiles, int_prd) for asic in tile],
        "AsicX":[asic.col for tile in tiles for asic in tile],
        "AsicY":[asic.row for tile in tiles for asic in tile],
        # asic data
        "Frq":[asic.fOsc for tile in tiles for asic in tile],
        "Start Time":[asic._startTime for tile in tiles for asic in tile],
        "Rel Time":[asic.relTimeNow for tile in tiles for asic in tile],
        "Rel Tick":[asic.relTicksNow for tile in tiles for asic in tile],
        # local data
        "Local Hits":[asic._localFifo._totalWrites for tile in tiles for asic in tile],
        "Local Max":[asic._localFifo._maxSize for tile in tiles for asic in tile],
        "Local Remain":[asic._localFifo._curSize for tile in tiles for asic in tile],
        # remote data
        "Remote Transactions":[asic._remoteFifo._totalWrites for tile in tiles for asic in tile],
        "Remote Max":[asic._remoteFifo._maxSize for tile in tiles for asic in tile],
        "Remote Remain":[asic._remoteFifo._curSize for tile in tiles for asic in tile],
    }

    # create the dataframe from from these dictionaries
    df = pd.DataFrame.from_dict(data)

    # save the dataframe into a json for safe keeping
    df.to_csv("output_df.csv")


if __name__ == "__main__":
    main()