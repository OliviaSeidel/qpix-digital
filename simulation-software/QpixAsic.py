#!/usr/bin/python3

import random
import math
import time
from enum import Enum

#Enum-like things
DIRECTIONS = ("North", "East", "South", "West")


class QPExcpetion(Exception):
  pass

class AsicState(Enum):
  Measure = 0
  TransmitLocal = 1
  TransmitRemote = 2

class QPByte:
  """
  NOTE: refactored PixelHit object! Data that are transferred are Bytes~ NOT
  'hits'. A hit is always a time stamp, but what is transferred is the more
  generic byte.

  This struct-style class stores no more than the 64 bit information transfered
  on a 64 bit Tx/Rx Endeavor protocol.
  """
  def __init__(self, hitTime, channelList, originRow, originCol, data=None):
    self.hitTime     = hitTime
    self.originRow   = originRow
    self.originCol   = originCol
    self.channelMask = 0
    # extra data to lug around for commands send to ASICs
    self.data = data
    for ch in channelList: 
      self.channelMask |= 0x1 << ch

  def AddChannel(self, channel):
    self.channelMask |= 0x1 << channel

class QPFifo:
  """
  FIFO class to store and manage incoming QPByte data between ASIC connections

  A FIFO can only do two things: Read and Write. Therefore, there should only 
  be two implemented public functions for this class: Read and Write.
  """
  def __init__(self, maxDepth=256):
    self._data = []
    self._maxSize = 0
    self._curSize = 0
    self._maxDepth = maxDepth
    self._full = False

  def Write(self, data=QPByte) -> int:
    """
    Implements a write feature to the Fifo
    ARGS:
      Ensure that the data being stored in the FIFO matches the QPByte
    Returns:
      current number of events stored in the FIFO
    """

    if not isinstance(data, QPByte):
      raise QPException("Can not add this data-type to a QPFifo!")

    self._data.append(data)
    self._curSize += 1

    if self._curSize > self._maxSize:
      self._maxSize = self._curSize

    if self._curSize > self._maxDepth:
      self._full = True

    return self._curSize

  def Read(self) -> QPByte:
    """
    Implements a Readout feature for the FIFO.
    ARGS:
      None
    Returns:
      oldest stored event (First In, First Out)
    """
    if self._curSize > 0:
      self._curSize -= 1
      return self._data.pop(0)
    else:
      return None

class ProcItem:
  '''
  Process item controlled by ProcQueue.
  0 - asic, the ASIC being pushed to
  1 - direction, where the data came from
  2 - QPByte, a QPByte object
  3 - inTime, time that the data would be received, or that the sending asic completes sending QPByte
  4 - command, flag to determine how individual ASIC receiving data should behave
  '''
  def __init__(self, asic, dir, QPByte, inTime, command=None):
    self.asic = asic
    self.dir = dir
    self.QPByte = QPByte
    self.inTime = inTime
    self.command = command
    self._nextItem = None

  def __gt__(self, otherItem):
    '''
    define that comparing process items based on what inTime the item should be
    processed
    '''
    if isinstance(otherItem, ProcItem):
      return self.inTime > otherItem.inTime
    else:
      return NotImplementedError

class ProcQueue:
  """
  ProcQueue class is the main class which defines the simulation flow. 
  
  It is designed to store ProcItem class objects, which are the basic unit of an ASIC transaction.
  """
  def __init__(self, procItem=None):
    self._curItem = procItem
    self._entries = 0

  def AddQueueItem(self, asic, dir, QPByte, inTime, command=None):
    '''
    refactor
    '''
    procItem = ProcItem(asic, dir, QPByte, inTime, command)
    self._AddQueueItem(procItem)

  def _AddQueueItem(self, procItem):
    '''
    include a new process item, inserting into list at appropriate time
    '''
    newItem = procItem
    curItem = self._curItem
    self._entries += 1

    if curItem is None:
      self._curItem = newItem
    elif curItem > newItem:
      h = self._curItem
      self._curItem = newItem
      self._curItem._nextItem = h
    else:
      while newItem > curItem and curItem._nextItem is not None:
        curItem = curItem._nextItem 
      newItem._nextItem = curItem._nextItem
      curItem._nextItem = newItem

    return self._entries

  def PopQueue(self):
    if self._curItem is None:
        return None
    self._entries -= 1
    data = self._curItem
    self._curItem = self._curItem._nextItem
    return data

  def SortQueue(self):
    '''
    deprecated
    '''
    pass

  def Length(self):
    return self._entries

class QPixAsic:
  """
  A Q-Pix ASIC fundamentally consists of:
  An oscillator of nominal frequency (~50 MHz)
  A number of channels (nominally 16 or 32)
    - When a given channel is "hit", a timestamp is generated
  Four communications interfaces to contatct nearest neighbors
  Each has its own queue

  fOsc       - Oscillator Frequency in Hz
  lastTsDir  - Last direction timestamp was accepted from
  state      - IDLE/MEASURING, - REPORT_LOCAL, - REPORT_REMOTE
  _localFifo   - Queue 0/1 are a ping/pong buffer mechanism
                   You switch from one to another upon receipt of a timestamp
  _curLocalQueue - Tells us whether we're in ping or pong state
  _remoteFifos  - A list of lists, one for each side, N E S W, which stores hits
  connections  - list of pointers to adjacent asics
  """
  def __init__(self, fOsc = 50e6, nPixels = 16, randomRate = 1.0/9.0, timeout = 0.5, row = None, col = None,
               isDaqNode = False, transferTicks = 4*66, debugLevel=0):
    # basic asic parameters
    self.nPixels        = 16
    self.fOsc           = fOsc
    self.tOsc           = 1.0/fOsc
    self._curLocalQueue = 0
    self.lastTsDir      = None
    self._maxLocalDepth = 0
    self.state          = AsicState.Measure
    self.randomRate     = randomRate
    self.row            = row
    self.col            = col
    self.connections    = [None] * 4 

    # timing, absolute and relative with random starting phase
    self.timeoutStart   = 0
    self.timeout        = timeout
    self.transferTicks  = transferTicks # why 264 transfer ticks?
    self.transferTime = self.transferTicks * self.tOsc
    self.lastAbsHitTime = [0] * self.nPixels
    self._absTimeNow    = 0
    self.relTimeNow     = (random.random()-0.5) * self.tOsc
    self.relTicksNow    = 0

    # daq node Configuration
    self.isDaqNode      = isDaqNode
    if self.isDaqNode:
      self.daqHits        = 0
      self.pixelData = {}

    # Queues / FIFOs
    self._localFifo   = QPFifo(maxDepth=256)
    self._remoteFifos  = [QPFifo(maxDepth=256)]  * 4

    # additional / debug
    self._debugLevel = debugLevel
<<<<<<< HEAD
    self._measurements = 0 # number of measurements made
    self._measuredTime = []
    self._localTransmissions = 0
    self._remoteTransmissions = 0
=======
>>>>>>> upstream/master
    self._hitReceptions = 0


  def __repr__(self):
    self.PrintStatus()
    return ""

  def PrintStatus(self):
    print("ASIC ("+str(self.row)+","+str(self.col)+") ", end="")
    print("STATE "+str(self.state),end='')
    # print("N_LOCAL(A,B) "+str(len(self._localFifo[0])) + "," + str(len(self._localFifo[1])),end='')
    print("N_REMOTE(N,E,S,W) ",end='')
    for d in range(4):
      print(str(len(self._remoteFifos[d])) + ",",end='')
    print("t = "+str(self._absTimeNow), ", trel ="+str(self.relTimeNow))
    print("ticks = "+str(self.relTicksNow))

  def CountConnections(self):
    nConnected = 0
    for conn in self.connections:
      if conn:
        nConnected += 1
    return nConnected

  def HasConnection(self, dir):
    if self.connections[dir]:
      return 1
    else:
      return 0

  def ReceiveData(self, queueItem:ProcItem):
    """
    Receive data from a neighbor
<<<<<<< HEAD
    queueItem - tuple of (asic, dir, hit, inTime)

    pixelData records the ticks from when the Daq receives data and the ticks 
    of the asic when it received the ask
    """
    inDir     = queueItem.dir # direction the signal came from
    inHit     = queueItem.pixelHit # the time the asic was asked
    inTime    = queueItem.inTime # the time the information will be received
=======
    queueItem - tuple of (asic, dir, byte, inTime)
    """
    inDir     = queueItem.dir
    inByte    = queueItem.QPByte
    inTime    = queueItem.inTime
>>>>>>> upstream/master
    inCommand = queueItem.command

    # how a DAQNode records and stores data
    if self.isDaqNode:
      print(f'compare {queueItem.inTime} with {self._absTimeNow}')
      self.UpdateTime(queueItem.inTime)
      self.daqHits += 1
      self._localFifo.Write(inByte)
      if self._debugLevel > 0:
        print(f"DAQ-{self.relTicksNow} ",end=' ')
        print(f"from: ({inByte.originRow},{inByte.originCol})",end='\n\t')
        print(f"Hit Time: {inByte.hitTime} "+format(inByte.channelMask,'016b'),end='\n\t')
        print(f"absT: {inTime}", end='\n\t')
        print(f"tDiff (ns): {(self.relTimeNow-inTime)*1e9:2.2f}")
        print(inByte)

      # store relevant data from the hit if necessary
<<<<<<< HEAD
      if hasattr(inHit, "data"):
        print(f'hit time of this data is {inHit.hitTime} with ticks {inHit.hitTime * self.fOsc}')
        pixel = f"({inHit.originRow},{inHit.originCol})"
        if pixel not in self.pixelData:
          self.pixelData[pixel] = []
        self.pixelData[pixel].append((self.relTicksNow, inHit.data))
        # print(f"received data! from asic {pixel}", inHit.data)
        print(f"the pixelData for asic {pixel} is {self.pixelData[pixel]} at lab time {self._absTimeNow} \n")
        
        # print(f'the time is {self._absTimeNow}')
        # print(f'the asic ticks are {self.relTicksNow} and sees time {self.relTimeNow}')
        
=======
      if hasattr(inByte, "data"):
        pixel = f"({inByte.originRow},{inByte.originCol})"
        if pixel not in self.pixelData:
          self.pixelData[pixel] = []
        self.pixelData[pixel].append((self.relTicksNow, inByte.data))

>>>>>>> upstream/master
      return []

    if self.connections[inDir] is None:
      print("WARNING receiving data from non-existent connection!")
    
    outList = [] 
    isFromDaq = bool(inByte.originCol is None and inByte.originRow is None)

    # 0: MEASURING STATE
    if self.state == AsicState.Measure:

      if isFromDaq:
        self.lastTsDir = inDir
        self.state = AsicState.TransmitLocal
        transactionCompleteTime = inTime + self.transferTime
        self.UpdateTime(transactionCompleteTime)
        self._measuredTime.append(self.relTimeNow)
        
        # Broadcast everything you receive from the DaqNode
        for i in range(4):
          if i != inDir and self.connections[i]:
            outList.append((self.connections[i] , (i+2)%4, inByte, transactionCompleteTime, inCommand))

        # Build hits on local queues for default inCommand
        if inCommand is None:
          self._GeneratePoissonHits(inTime)
        # alternative responses to incoming daq nodes here
        else:
          self._command = inCommand
      else:
        print("WARNING lost data! Can't send data while measuring!")

    # Receive in other states, means queue up hits
    else:
      # Don't forward source timestamps
      if inByte.originRow is not None and inByte.originCol is not None:
        self._remoteFifos[inDir].Write(inByte)

    return outList

  def _GeneratePoissonHits(self, targetTime):
    """
    Generate Poisson hits for the time step ##
    Distribution of inter-arrival times can be modeled by throwing
    p = Uniform(0,1) and feeding it to -ln(1.0 - p)/aveRate
    General strategy for moving forward to some timestep is:
      for each channel:
        currentTime = now
        while currentTime < targetTime:
          generate nextHitTime from distribution above
          if currentTime + nextHitTime < targetTime:
            Calculate number of ticks for timestamp and add it to the current queue
          else:
            this is last hit for this pixel, add the next time to the alternate queue
      Sort the overall list by timestamp
      foreach unique entry in the timestamp list, create a hit with proper parameters,
      add it to the queue (A or B)
    """
    newHits = []

    for ch in range(self.nPixels):
      currentTime = self.lastAbsHitTime[ch]
      while currentTime < targetTime:

        # generate a posion distribution of absolute / reletive times
        p = random.random() #prints random real between 0 and 1
        nextAbsHitTime = currentTime + (-math.log(1.0 - p) / self.randomRate)
        nextRelHitTime = int(math.floor(nextAbsHitTime / self.tOsc))

        # if hit happens before target time, add a new hit to the list
        if nextAbsHitTime < targetTime:
          newHits.append([ch, nextRelHitTime])
          currentTime = nextAbsHitTime
          self.lastAbsHitTime[ch] = currentTime
        elif nextAbsHitTime > targetTime:
          currentTime             = targetTime
          self.lastAbsHitTime[ch] = targetTime

    if not newHits:
      return 0

    # sort the new hits by time, group the channels with the same hit time, then add
    # them into the FIFO
    newHits.sort(key=lambda x : x[1], reverse=False)
    prevByte = QPByte(newHits[0][1], [newHits[0][0]], self.row, self.col)
    for ch, hitTime in newHits[1:]:
      if hitTime == prevByte.hitTime:
        prevByte.AddChannel(ch)
      else:
        self._localFifo.Write(prevByte)
        prevByte = QPByte(hitTime, [ch], self.row, self.col)

    return len(newHits)

  def Process(self, targetTime):
    """
    Transmits local and remote data when asked 
    """
    # nothing to process if DAQ or if target time is in past
    if self.isDaqNode or self._absTimeNow > targetTime:
      self.UpdateTime(targetTime)
      self.state = AsicState.Measure
      return []

    # Process incoming commands first
    if hasattr(self, "_command") and self._command is not None:
      self._command = None
      # all commands build local queues, and the command should build up any 'hit' of interest
<<<<<<< HEAD
      self.state = 1 #transmit local state
      self._localQueues[(self._curLocalQueue+1)%2].append(PixelHit(self._measuredTime[-1], [], self.row, self.col, data=self.relTicksNow)) #relTicks now is the total number of ticks of the ASIC

    if self.state == AsicStates.Measure.value:
      return self._processMeasuringState(targetTime)

    if self.state == AsicStates.TransmitLocal.value:
      # print(f'processing transmission from local state for asic ({self.row}, {self.col})')
      return self._processTransmitLocalState(targetTime)

    if self.state == AsicStates.TransmitRemote.value:
      # print(f'processing transmission from remote state for asic ({self.row}, {self.col})')
=======
      self.state = AsicState.TransmitLocal
      self._localFifo.Write(QPByte(self._measuredTime, [], self.row, self.col, data=self.relTicksNow)) #relTicks now is the total number of ticks of the ASIC

    if self.state == AsicState.Measure:
      return self._processMeasuringState(targetTime)

    if self.state == AsicState.TransmitLocal:
      return self._processTransmitLocalState(targetTime)

    if self.state == AsicState.TransmitRemote:
>>>>>>> upstream/master
      return self._processTransmitRemoteState(targetTime)

    else:
      # undefined state
      print("WARNING! ASIC in undefined state")
      self.state = AsicState.Measure
      return []

  def _processMeasuringState(self, targetTime):
    """
    helper function when processing in Measuring state
    """
    self.UpdateTime(targetTime)
    return []

  def _processTransmitLocalState(self, targetTime):
    """
    helper function for sending local data where it needs to go
    sends a single local state queue item into the outlist
    """

    outList = [] # list to send out
    transactionCompleteTime = self._absTimeNow + self.transferTime
    # print(f'transaction of local data complete in {transactionCompleteTime} for asic ({self.row}, {self.col})')

    # read an event from our local FIFO, if there is something in it, transmit it
    hit = self._localFifo.Read()
    if hit is not None:
      outList.append((self.connections[self.lastTsDir], (self.lastTsDir+2)%4, hit, transactionCompleteTime))
      self.UpdateTime(transactionCompleteTime)
    else:
      self.state = AsicState.TransmitRemote
      self.timeoutStart = self._absTimeNow

    return outList

  def _processTransmitRemoteState(self, targetTime):
    """
    helper function for sending remote data where it needs to go
    sends a single remote queue item from one of the remote queues 
    """

    # If we're timed out, just kill it
    if self._absTimeNow - self.timeoutStart > self.timeout:
      self.state = AsicState.Measure
      if self._localFifo._curSize > 0:
          print("Lost "+str(len(self._localFifo._curSize))+" hits that were left to forward!")
      return []

    hitsToForward = False
    for remote_fifo in self._remoteFifos:
      if remote_fifo._curSize > 0:
        hitsToForward = True

    # If there's nothing to forward, just bring us up to requested time
    if not(hitsToForward):
      self.UpdateTime(targetTime)
      if self._absTimeNow - self.timeoutStart > self.timeout:
        self.state = AsicState.Measure
      return []

    else:
      outList = []
      completeTime = self._absTimeNow + self.transferTime
      for remote_fifo in self._remoteFifos:
        hit = remote_fifo.Read()
        if hit is not None:
          outList.append((self.connections[self.lastTsDir], (self.lastTsDir+2)%4 , hit, completeTime))
          self.UpdateTime(completeTime)

      return outList

  def UpdateTime(self, absTime):
    """
    absTime - the time an asic is asked for data

    function keeps track of updating absTime and performs necessary updates to
    relTime and relTicksNow any time that absTime is updated. 
    
    Direct assignments should not be made to absTime
    """
    self._absTimeNow = absTime

    # only update the relTime if the asic needs to
    if self._absTimeNow > self.relTimeNow:
      t_diff =  self._absTimeNow - self.relTimeNow 
      cycles = int(t_diff/self.tOsc) + 1

      # update the local clock cycles
      self.relTimeNow += cycles * self.tOsc
      self.relTicksNow += cycles