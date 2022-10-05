import pytest
import QpixAsic
import QpixAsicArray
import numpy as np

from QpixAsic import AsicWord
from QpixAsic import AsicDirMask
from QpixAsic import AsicState

# make testing default input parameters to QpixAsicArray
tRows = 2
tCols = 2
nPix = 16
fNominal = 50e6
pctSpread = 0.05
deltaT = 1e-5
timeEpsilon = 1e-6
timeout = 15e4
hitsPerSec = 20./1.
debug = 0.0
tiledf = None
nTicks = 4*66
debug = 0
pTimeout = fNominal/2
## test arguments
dTime = 1e-3


## fixtures
@pytest.fixture
def qpix_array():
    """
    Creates the default QpixAsicArray for the test bed.
    """
    return QpixAsicArray.QpixAsicArray(
                nrows=tRows, ncols=tCols, nPixs=nPix,
                fNominal=fNominal, pctSpread=pctSpread, deltaT=deltaT,
                timeEpsilon=timeEpsilon, timeout=timeout,
                hitsPerSec=hitsPerSec, debug=debug, tiledf=tiledf)

@pytest.fixture
def qpix_asic():
    """
    Create a default, isolated ASIC
    """
    return QpixAsic.QPixAsic(fOsc=fNominal, nPixels=nPix, randomRate=hitsPerSec, 
                             timeout=timeout, row=None, col=None, isDaqNode=False,
                            transferTicks=nTicks, debugLevel=debug, pTimeout=pTimeout)

@pytest.fixture
def tProcRegReq(qpix_array):
    """
    Create a default register request based on the default asic array
    """
    tAsic = qpix_array[0][0]
    tRegReqByte = QpixAsic.QPByte(AsicWord.REGREQ, None, None, ReqID=2)
    tProcRegReq = QpixAsic.ProcItem(tAsic, 0, tRegReqByte, 0)
    return tProcRegReq

@pytest.fixture
def tRegReqByte():
    """
    Create a interogation packet to send to a specific asic
    """
    tRegReqByte = QpixAsic.QPByte(AsicWord.REGREQ, None, None, ReqID=2)
    return tRegReqByte


######################
##  Test Functions  ##
######################
def test_count_array_connections(qpix_array):
    """
    sum up the connections to ensure they make sense
    """
    nConnections, nTrue = 0,0
    for i in range(qpix_array._ncols):
        for j in range(qpix_array._nrows):
            nConnections += qpix_array[i][j].CountConnections()

            # how many horizontal connections there should be
            if i == 0 or i == qpix_array._ncols - 1:
                nTrue += 1
            else:
                nTrue += 2

            # how many vertical connections there should be
            if i == 0 or i == qpix_array._nrows - 1:
                nTrue += 1
            else:
                nTrue += 2

    # include daqnode connection
    assert nConnections == nTrue+1, \
        f"{nConnections} qpa of {qpix_array._nrows},{qpix_array._ncols} mismatch"



def test_asic_receiveByte(qpix_array, tProcRegReq):
    """
    test basic receiveByte condition
    """
    tAsic = qpix_array[0][0]
    tProcRegReq.dir = AsicDirMask.West
    assert tAsic.state == AsicState.Idle, "should begin in idle state"
    b = tAsic.ReceiveByte(tProcRegReq)
    assert len(b) == 2, f"{len(b)}, should create two transactions"
    assert tAsic.state == AsicState.TransmitLocal, "should transmit after receiving byte from DAQ node"

def test_asic_injectHitsInterrogate(qpix_array, tRegReqByte):
    """
    Make sure that asic receives a interogation command, fills the local fifo
    with all of the hits it should.
    """
    # hits to inject
    nHits = 10
    inTime = 1e-4
    hits = np.arange(1e-9, inTime, inTime/nHits)
    # select asic to test
    tAsic = qpix_array[1][1]
    tAsic.InjectHits(hits)
    proc = QpixAsic.ProcItem(tAsic, QpixAsic.AsicDirMask.North, tRegReqByte, inTime, command="Interrogate")
    b = tAsic.ReceiveByte(proc)
    fifoHits = tAsic._localFifo._curSize
    assert fifoHits == nHits, f"inject hits {len(hits)} failed to put all hits within local FIFO {fifoHits} for interrogate"

def test_asic_process_push(qpix_array):
    """
    TODO: test various injectHits and process conditions
    """
    tAsic = qpix_array[0][0]
    endTime = 1e-3
    hits = np.arange(0, endTime, 1e-5)
    tAsic.InjectHits(hits)
    nHits = 0
    curT = 0

    # push should allow all of the hits to come through
    tAsic.config.EnablePush = True
    while nHits < len(hits) and tAsic._absTimeNow <= endTime:
        h = tAsic.Process(curT)
        curT += deltaT
        nHits += len(h)
    assert nHits == len(hits), "processing did not generate transactions for all injected hits"
    assert tAsic._absTimeNow - tAsic.tOsc <= endTime, "processing of injected hits took too long"
    nEvts = len(hits)
    nStates = len(tAsic.state_times) 
    assert nStates == nEvts, f"{nStates} not equivalents to {nEvts}"

def test_asic_updateTime(qpix_array):
    tAsic = qpix_array[0][0]
    tAsic.UpdateTime(dTime)
    tAsic.UpdateTime(dTime)
    tAsic.UpdateTime(dTime)
    assert tAsic._absTimeNow == dTime, "updating time incorrect. abstime should update to current time"
    assert tAsic.relTimeNow - tAsic.tOsc <= dTime, f"rel time not within one clk cycle of dest time"
    assert isinstance(tAsic.relTicksNow, int), "updating time incorrect. ticks are int"

## test constructors last to ensure that basic construction hasn't changed from
#previous implementations
def test_array_constructor(qpix_array):
    assert qpix_array._nrows == tRows, "Asic Array not creating appropriate amount of rows"
    assert qpix_array._ncols == tCols, "Asic Array not creating appropriate amount of cols"
    assert qpix_array._nPixs == nPix, "Asic Array not creating correct amount of pixels"
    assert isinstance(qpix_array._queue, QpixAsic.ProcQueue), "Array requires processing queue"

def test_asic_constructor(qpix_array):
    tAsic = qpix_array[0][0]
    assert tAsic.nPixels == nPix, "incorrect amount of pixels on ASIC"
    assert isinstance(tAsic.config, QpixAsic.AsicConfig), "asic config, incorrect type"

def test_asic_time_update(qpix_asic):
    tAsic = qpix_asic
    dT = 2e-6
    tAsic.UpdateTime(dT)
    tAsic.UpdateTime(dT/2)
    assert tAsic._absTimeNow == dT, "update time function not working"

if __name__ == "__main__":
    qpix_array = QpixAsicArray.QpixAsicArray(
                nrows=tRows, ncols=tCols, nPixs=nPix,
                fNominal=fNominal, pctSpread=pctSpread, deltaT=deltaT,
                timeEpsilon=timeEpsilon, timeout=timeout,
                hitsPerSec=hitsPerSec, debug=debug, tiledf=tiledf)

    ## test full readout of 10 hits
    nHits = 10
    inTime = qpix_array[0][0].transferTime + qpix_array[0][1].transferTime

    hits = np.arange(1e-9, inTime, inTime/nHits) # don't start at 0 time
    # select asic to test
    tAsic = qpix_array[1][1]
    # asic right after inject hits
    prevState = tAsic.state
    print(f"initial ASIC, ASIC now in state: {tAsic.state} @ {tAsic._absTimeNow:0.2e}")
    tAsic.InjectHits(hits)

    # asic right after inject hits
    prevState = tAsic.state
    print(f"inject hits, ASIC now in state: {tAsic.state} @ {tAsic._absTimeNow:0.2e}")

    tRegReqByte = QpixAsic.QPByte(AsicWord.REGREQ, None, None, ReqID=2)
    proc = QpixAsic.ProcItem(tAsic, QpixAsic.AsicDirMask.North, tRegReqByte, inTime, command="Interrogate")
    b = tAsic.ReceiveByte(proc)
    fifoHits = tAsic._localFifo._curSize

    # how to handle parallel transfers??
    # asic right after receive byte
    prevState = tAsic.state
    eT = inTime + tAsic.transferTime
    print(f"receive byte, ASIC now in state: {tAsic.state} @ {tAsic._absTimeNow:0.2e} - expected {eT:0.2e}")

    # process away all of the local hits generated
    while fifoHits > 0:
        dT = tAsic._absTimeNow + deltaT
        _ = tAsic.Process(dT)
        fifoHits = tAsic._localFifo._curSize

    # transmit local
    eT += tAsic.transferTime * nHits
    prevState = tAsic.state
    print(f"Fifo hits are empty, ASIC now in state: {tAsic.state} @ {tAsic._absTimeNow:0.2e} - expected {eT:0.2e}")

    while tAsic.state == prevState:
        dT = tAsic._absTimeNow + deltaT
        _ = tAsic.Process(dT)

    # transmit finish
    prevState = tAsic.state
    print(f"state change, ASIC now in state: {tAsic.state} @ {tAsic._absTimeNow:0.2e} - expected {eT:0.2e}")

    # this should be the finish state
    while tAsic.state == prevState:
        dT = tAsic._absTimeNow + deltaT
        _ = tAsic.Process(dT)

    # transmit remote
    eT += tAsic.transferTime * 1
    prevState = tAsic.state
    print(f"state change, ASIC now in state: {tAsic.state} @ {tAsic._absTimeNow:0.2e} - expected {eT:0.2e}")

    while tAsic.state == prevState:
        dT = tAsic._absTimeNow + deltaT
        _ = tAsic.Process(dT)

    # back to IDLE
    eT += tAsic.tOsc * tAsic.config.timeout
    prevState = tAsic.state
    print(f"state change, ASIC now in state: {tAsic.state} @ {tAsic._absTimeNow:0.2e} - expected {eT:0.2e}")