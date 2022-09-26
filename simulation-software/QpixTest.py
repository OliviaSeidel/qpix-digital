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


######################
##  Test Functions  ##
######################
def test_asic_receiveByte(qpix_array, tProcRegReq):
    """
    TODO: test various receiveByte conditions
    """
    tAsic = qpix_array[0][0]
    tProcRegReq.dir = AsicDirMask.West
    assert tAsic.state == AsicState.Idle, "should begin in idle state"
    b = tAsic.ReceiveByte(tProcRegReq)
    assert len(b) == 2, f"{len(b)}, should create two transactions"
    assert tAsic.state == AsicState.TransmitLocal, "should transmit after receiving byte from DAQ node"

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

if __name__ == "__main__":
    tProcRegReq.dir = AsicDirMask.West
    b = tAsic.ReceiveByte(tProcRegReq)