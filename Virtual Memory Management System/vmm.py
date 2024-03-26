#!/usr/bin/python

from utils import *
from vmmmisc import *
import sys
import threading
import time
import random
import math
import os

memorySize = int(sys.argv[2])
pageSize = 1024
P = noPages = int(memorySize / pageSize)
B = noBitsForPage = int(math.log(P, 2))

process = {}
memory = [(-1, -1)] * P
readyqueue = []
blockedqueue = []
runningPID = -1
requests = {}
SIGUSR1 = SignalUser1()
memoryAccessEvent = threading.Event()

def getPageNo(vaddr):
    return int(hextobin(vaddr)[-16:-10], 2)

def scheduler():
    global runningPID
    while len(readyqueue) > 0:
        time.sleep(5)
        if len(readyqueue) > 0:  # Check if the ready queue is not empty
            runningPID = readyqueue.pop(0)  # Changed to pop from the beginning of the queue
            memoryAccessEvent.set()
        else:
            os._exit(0)  # Changed to os._exit(0) for proper termination

def processInit(pid):
    process[pid] = [{"p": 0, "m": 0, "f": -1}] * 64  # Simplified process initialization
    requests[pid] = []
    readyqueue.append(pid)

def SIGUSR1_Handler(pidin, pagein):
    blockedqueue.append(pidin)
    print("Blocked queue:  ", blockedqueue)
    pid, page, frame = getSwapCandidate()
    if pid == -1 or page == -1:
        pass
    else:
        if process[pid][page]["m"] == 1:
            time.sleep(1)
        print("Swapping.\t pid: ", pid, ", page: ", page, ", frame: ", frame)
        process[pid][page]["p"] = 0
        memory[frame] = (-1, -1)
        time.sleep(1)
    print("Loading.\t pid: ", pidin, ", page: ", pagein, ", frame: ", frame)
    time.sleep(1)
    setEntry(pidin, pagein, frame)
    t = blockedqueue.pop(0)
    if len(requests[t]) > 0:
        if t not in readyqueue:  # Check if the process is already in the ready queue
            readyqueue.append(t)
    print("Ready queue:    ", readyqueue)

def setEntry(pid, page, frame):
    memory[frame] = (pid, page)
    process[pid][page]["p"] = 1
    process[pid][page]["f"] = frame

def getEntry(pid, page):
    if process[pid][page]["p"] == 1:
        frameNo = process[pid][page]["f"]
    else:
        raise FrameNotFoundError(pid, page)
    if frameNo == -1:
        raise FrameNotFoundError(pid, page)
    return frameNo

def useEntry(pid, page, rw):
    if rw == 'W':
        process[pid][page]["m"] = 1

def getSwapCandidate():
    try:
        i = memory.index((-1, -1))
        return (-1, -1, i)
    except ValueError as e:
        i = random.randint(0, P-1)
        t = memory[i]
        return (t[0], t[1], i)

def v2p(pid, vaddr):
    try:
        frameNo = getEntry(pid, getPageNo(vaddr))
        paddr = bintohex(inttobin(frameNo) + hextobin(vaddr)[-10:])
        print("Direct Access. \t " + paddr + "\n")
        return paddr
    except (FrameNotFoundError, AddressTranslationError) as e:
        print(f"Error: {e}")
        return None

def mmu():
    while True:
        memoryAccessEvent.wait()
        memoryAccessEvent.clear()
        if len(requests[runningPID]) > 0:
            pid = runningPID
            rw, vaddr = requests[pid].pop(0)
            print("Scheduling.\t pid: ", pid, "\tvaddr: ", vaddr)
            paddr = v2p(pid, vaddr)

            if paddr is not None:
                print("Direct Access. \t " + paddr + "\n")
                useEntry(pid, getPageNo(vaddr), rw)
            else:
                print(f"Error: Unable to perform memory access for pid: {pid}, vaddr: {vaddr}")
                SIGUSR1.set(pid, getPageNo(vaddr))
                SIGUSR1.send(SIGUSR1_Handler)
                continue

            print('Main Memory:\t | ', end="")
            for i in range(0, len(memory)):
                if memory[i][0] == -1:
                    print("-", end=" | ")
                else:
                    print(memory[i][0], end=" | ")
            print("\n")

f = open(sys.argv[1], 'r')
requestList = f.readlines()
f.close()

for entry in requestList:
    pid, rw, vaddr = entry.split(',')
    pid = int(pid)
    rw = rw.strip()
    vaddr = vaddr.strip()
    if pid not in process:
        processInit(pid)
    requests[pid].append((rw, vaddr))

thread_mmu = threading.Thread(target=mmu)
thread_os_scheduler = threading.Thread(target=scheduler)
thread_os_scheduler.start()
thread_mmu.start()
