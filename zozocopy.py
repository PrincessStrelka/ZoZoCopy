import argparse
import shutil
import os
import pathlib
import datetime
import os
import time
import subprocess
import re
import argparse
import datetime
import json
import pathlib
import platform
import subprocess
import sys
import typing
import numpy
import pandas
import random          
from time import strftime, localtime
import re
from pathlib import Path

#sudo python3 zozocopy.py "/dev/nvme0n1p2" "/home/zoey/Desktop/source" "/home/zoey/Desktop/test"

#create the parser objects
parser = argparse.ArgumentParser(prog='ZoZoCopy', description='Copies data from a NTFS3 drive to an EXT4 drive whilst preserving the metadata.', epilog=':3')
parser.add_argument('dev_path')
parser.add_argument('src_folder')
parser.add_argument('dst_folder')
parser.add_argument('should_print')
args = parser.parse_args()
should_print = args.should_print.lower() in ['true', '1', 't', 'y', 'yes', 'yeah', 'yup', 'certainly', 'uh-huh']
src_folder = os.path.join(args.src_folder, '')
dst_name = datetime.datetime.now().strftime(f"_%Y-%m-%d_%H.%M.%S")
dst_folder = os.path.join(args.dst_folder, '') + args.src_folder.split(os.sep)[-1] + dst_name + os.sep

#make sure the destination folder exists
print("Set up destination folder")
os.system(f"cp '{src_folder}' '{dst_folder}' -p -r --sparse=always -a")  

#set up the list of files to copy and their destination
print("Create files to copy list")
filesToCopy = []
for root, dirs, files in os.walk(src_folder):    
    filesToCopy.append([root, root.replace(src_folder, dst_folder)])
    for file in files:
        sourceFilePath = os.path.join(root, '') + file
        filesToCopy.append([sourceFilePath, sourceFilePath.replace(src_folder, dst_folder)])

#itterate through all the files we need to copy
approxTimePerFile = 0.746416178
start_time = time.time()
totalFileCount = len(filesToCopy)

def getTimeFromStatList(gtfsllist, Label, offset):
    #search for the matching entry in stat
    templist = [k for k in gtfsllist if Label in k][offset][8:-6].split(".")
    
    #if the entry has a date
    if len(templist) > 1 :
        #get epoch
        templist[0] = int(datetime.datetime.strptime(templist[0], "%Y-%m-%d %H:%M:%S").timestamp())
        #get nanosecond epoch
        templist.insert(0, templist[0]*1000000000 + int(templist[1]))     
        #get inode times
        timeNs = templist[0]
        adjusted = timeNs // 1000000000 + 2147483648
        inode_time = (adjusted % 4294967296) - 2147483648
        inode_extra = int(((int(timeNs % 1000000000) & 0x3fffffff) << 2) + int(adjusted / 4294967296))
        templist[1] = inode_time
        templist[2] = inode_extra

    else:
        templist[0] = None

    return templist

#profile times
def addMarker(label, list):
    #print(f'\033[30m{label}\033[0m: {time.time()-timeKeystone}')
    list.append([label, time.time()-timeKeystone])
    return time.time()
    
#itterate through all files
avgtimes = []
while len(filesToCopy) > 0:
    timeKeystone = time.time()
    for f in filesToCopy:
        thisloop = []        
        timeKeystone = addMarker("start loop", thisloop)
        
        srcfile = f[0]
        dstfile = f[1]    
        #get the stat of source file
        srcstat = str(subprocess.run(["stat", f"{srcfile}"], capture_output=True, text=True).stdout)        

        #get source times into a list
        srcStatList = srcstat.split("\n")

        timesList = []
        src_atimeNs  = getTimeFromStatList(srcStatList, "Access", -1)
        if src_atimeNs[0] != None : timesList.append(src_atimeNs)    
        src_mtimeNs  = getTimeFromStatList(srcStatList, "Modify", 0)
        if src_mtimeNs[0] != None : timesList.append(src_mtimeNs)    
        src_ctimeNs  = getTimeFromStatList(srcStatList, "Change", 0)
        if src_ctimeNs[0] != None : timesList.append(src_ctimeNs)    
        src_crtimeNs  = getTimeFromStatList(srcStatList, "Birth", 0)
        if src_crtimeNs[0] != None : timesList.append(src_crtimeNs)
        
        #sort the times list by nanoseconds
        timesList.sort()
        
        #add the times to a dictionary, if they dont exist, use the shortest time in timeslist instead
        fallthroughTime = timesList[0]
        timeDict = {
            "atime" : src_atimeNs if src_atimeNs[0] != None else fallthroughTime,
            "mtime" : src_mtimeNs if src_mtimeNs[0] != None else fallthroughTime,
            "ctime" : src_ctimeNs if src_ctimeNs[0] != None else fallthroughTime,
            "crtime": src_crtimeNs if src_crtimeNs[0] != None else fallthroughTime,
        }
        timeKeystone = addMarker("get source stats", thisloop)
        
        #copy the source times to the dest file
        for key, value in timeDict.items():
            #print(key, value[1], value[2])
            d_field = key
            d_epoch = value[1]
            d_extra = value[2]
            #print(d_field, d_epoch, d_extra)
            subprocess.run(["debugfs", "-w", "-R", f'set_inode_field <{os.stat(dstfile).st_ino}> {key} @{d_epoch}', args.dev_path], capture_output=True)
            subprocess.run(["debugfs", "-w", "-R", f'set_inode_field <{os.stat(dstfile).st_ino}> {key}_extra {hex(d_extra)}', args.dev_path], capture_output=True)    
        timeKeystone = addMarker("copy the source stats", thisloop)

        #get the stat of dest file
        dststatfs = subprocess.run(["debugfs", "-R", f'stat <{os.stat(dstfile).st_ino}>', args.dev_path], capture_output=True, text=True).stdout    
        dststatList = [k for k in dststatfs.split("\n") if "time" in k]
        timeKeystone = addMarker("get dest stats", thisloop)
        
        #check if times match
        timesmatch = True
        for d in dststatList:
            srcd = timeDict[d[:6].strip()]
            d = d[10:-28].split(":")        
            if not int(d[0], 16) == srcd[1] and int(d[1], 16) == srcd[2]: timesmatch = False
        
        #print stats if error        
        if timesmatch:                   
            filesToCopy.remove(f)
        timeKeystone = addMarker("check if times match", thisloop)

        #progress output
        #timesmatch = False
        print(f'[{len(filesToCopy)}] \033[34m{srcfile.replace(os.sep.join(src_folder.split(os.sep)[:-2]), "")}\033[0m to \033[{32 if timesmatch else 31}m{dstfile.replace(args.dst_folder,"")}\033[0m')        
        timeKeystone = addMarker("end loop", thisloop)
        avgtimes.append(thisloop)
        
print("flush caches and retry failed files")
subprocess.run(["sync"], capture_output=True)
subprocess.run(["sysctl", "-w", "vm.drop_caches=3"], capture_output=True)
print(f' --- Completed {totalFileCount} Files in {(time.time() - start_time)} Seconds. {(time.time() - start_time)/totalFileCount} per file speed ---')

print("average section times:")
rows = len(avgtimes[0])
sortedAvg = []
alltotal = 0
for i in range(0, rows):
    total = 0
    for j in avgtimes:
        #print(j[i][1])
        total += j[i][1]
    avg = total / len(avgtimes)
    sortedAvg.append([avg, avgtimes[0][i][0]])
    alltotal += (avg)
    #print(f'\033[30m{avgtimes[0][i][0]}\033[0m: {avg}')

sortedAvg.sort(reverse=True)
for s in sortedAvg:
    print(f'{s[1]}: \033[30m{s[0]}\033[0m | {round(s[0]/alltotal*100, 4)}%')

'''

for f in filesToCopy:
    thisLoopProfile = []
    timeKeystone = timeProfile("Start Loop", thisLoopProfile)

    copydatsource = f[0]
    copydatdest = f[1]                

    #get the stat of source file
    sourceStat = str(subprocess.run(["stat", f"{copydatsource}"], capture_output=True, text=True).stdout)        
    timeKeystone = timeProfile("get source stat time", thisLoopProfile)
    
    #get times of source file into a list
    timesList = []
    for t in [["Access", "atime"], ["Modify", "mtime"], ['Change', "ctime"], ['Birth', "crtime"]]:
        fieldString = list(filter(lambda x: t[0] in x, sourceStat.split("\n")))[-1]
        fieldDateList = fieldString[8:-6].split(".")
        fieldNs = (int(datetime.datetime.strptime(fieldDateList[0], "%Y-%m-%d %H:%M:%S").timestamp())*10**9) + int(fieldDateList[1]) if len(fieldDateList)>1 else None
        timesList.append([t[1], fieldNs])

    timeKeystone = timeProfile("get times of source file as list time", thisLoopProfile)
    
    #convert times into inode field times
    fallthroughTime = min([num[1] for num in timesList if isinstance(num[1], (int,float))])            
    for t in timesList:            
        field = t[0]
        timeNs = t[1] if not t[1] == None else fallthroughTime                        
        
        adjusted = timeNs // 1000000000 + 2147483648
        inode_time = (adjusted % 4294967296) - 2147483648
        inode_extra = int(((int(timeNs % 1000000000) & 0x3fffffff) << 2) + int(adjusted / 4294967296))
        
        subprocess.run(["debugfs", "-w", "-R", f'set_inode_field <{os.stat(copydatdest).st_ino}> {field} @{hex(inode_time)}', args.dev_path], capture_output=True)
        subprocess.run(["debugfs", "-w", "-R", f'set_inode_field <{os.stat(copydatdest).st_ino}> {field}_extra {hex(inode_extra)}', args.dev_path], capture_output=True)    
    timeKeystone = timeProfile("convert times list into inode and write inodes time", thisLoopProfile)
    
    #if the times dont match, print the stats and move to the end of the list, else, remove this file from the ones to process
    #filesToCopy.remove(f)
    destcol = 32
    if retry:
        if should_print:
            print(f'\033[34m{sourceStat}\033[0m')
            print(f'\033[35m{destStat}\033[0m')
        destcol = 31
        filesToCopy.append(f)
        totalFileCount+=1           
    print(f'[ / ] [~ s remaining] \033[34m{copydatsource.replace(os.sep.join(src_folder.split(os.sep)[:-2]), "")}\033[0m to \033[{destcol}m{copydatdest.replace(args.dst_folder,"")}\033[0m')        

    timeKeystone = timeProfile("print error check time", thisLoopProfile)
    timeProfiling.append(thisLoopProfile)

#refresh the caches
print("flush the caches")
subprocess.run(["sync"], capture_output=True)
subprocess.run(["sysctl", "-w", "vm.drop_caches=3"], capture_output=True)

print("verifying file copy")'''
