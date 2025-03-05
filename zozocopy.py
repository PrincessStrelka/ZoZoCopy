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

#ensure the failed.txt exists
myfile = open("failed.txt", "a")
myfile.write(f" ---- {dst_folder} ---- \n")

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
start_time = time.time()
totalFileCount = len(filesToCopy)
while len(filesToCopy)>0:
    for f in filesToCopy:
        copydatsource = f[0]
        copydatdest = f[1]                
                
        #get the stat of source file
        sourceStat = str(subprocess.run(["stat", f"{copydatsource}"], capture_output=True, text=True).stdout)        
        
        #get times of source file into a list
        timesList = []
        for t in [["Access", "atime"], ["Modify", "mtime"], ['Change', "ctime"], ['Birth', "crtime"]]:
            fieldString = list(filter(lambda x: t[0] in x, sourceStat.split("\n")))[-1]
            fieldDateList = fieldString[8:-6].split(".")
            fieldNs = (int(datetime.datetime.strptime(fieldDateList[0], "%Y-%m-%d %H:%M:%S").timestamp())*10**9) + int(fieldDateList[1]) if len(fieldDateList)>1 else None
            timesList.append([t[1], fieldNs])
        
        #convert times into inode field times
        fallthroughTime = min([num[1] for num in timesList if isinstance(num[1], (int,float))])            
        for t in timesList:            
            field = t[0]
            timeNs = t[1] if not t[1] == None else fallthroughTime
            #print(f'{field.rjust(6)}: {timeNs}')
            
            #get the nanoseconds
            nanosec = int(timeNs % 1000000000)
            nanosec = (nanosec & 0x3fffffff) << 2
            
            #get the epoch
            epoch = int(timeNs // 1e9)
            adjusted = epoch + 2147483648
            time_lowbits=(( (adjusted % 4294967296) - 2147483648 ))
            time_highbits= int(adjusted / 4294967296)

            #create the extra feild
            extra_field= int(nanosec + time_highbits)
            subprocess.run(["debugfs", "-w", "-R", f'set_inode_field <{os.stat(copydatdest).st_ino}> {field} @{hex(time_lowbits)}', args.dev_path], capture_output=True)
            subprocess.run(["debugfs", "-w", "-R", f'set_inode_field <{os.stat(copydatdest).st_ino}> {field}_extra {hex(extra_field)}', args.dev_path], capture_output=True)    
            
        #refresh the caches
        #os.system('sudo sync && sudo sysctl -w vm.drop_caches=3')
        subprocess.run(["sync"], capture_output=True)
        subprocess.run(["sysctl", "-w", "vm.drop_caches=3"], capture_output=True)
    
        #get the stat of copied file
        destStat = str(subprocess.run(["stat", f"{copydatdest}"], capture_output=True, text=True).stdout)        

        #verify that the times have been correctly coppied
        j=0
        retry = False
        for t in [["Access", "atime"], ["Modify", "mtime"], ['Change', "ctime"], ['Birth', "crtime"]]:
            fieldString = list(filter(lambda x: t[0] in x, destStat.split("\n")))[-1]
            fieldDateList = fieldString[8:-6].split(".")
            fieldNs = (int(datetime.datetime.strptime(fieldDateList[0], "%Y-%m-%d %H:%M:%S").timestamp())*10**9) + int(fieldDateList[1]) if len(fieldDateList)>1 else None
            correctNs = timesList[j][1] if not timesList[j][1] == None else fallthroughTime
            timesMatch = fieldNs == correctNs
            if should_print:
                print(f'{t[1].replace("time", "")}: \033[32m{correctNs}\033[0m \033[{32 if timesMatch else 31}m{fieldNs}\033[0m ', end="")
            if not timesMatch : retry = True
            j+=1
        if should_print:
            print()

        #if the times dont match, print the stats and move to the end of the list, else, remove this file from the ones to process
        filesToCopy.remove(f)
        destcol = 32
        if retry:
            if should_print:
                print(f'\033[34m{sourceStat}\033[0m')
                print(f'\033[35m{destStat}\033[0m')
            destcol = 31
            filesToCopy.append(f)
            totalFileCount+=1        
        print(f'[{totalFileCount-len(filesToCopy)+1}/{totalFileCount}] [Runtime: {round((time.time() - start_time), 4)}s] \033[34m{copydatsource.replace(os.sep.join(src_folder.split(os.sep)[:-2]), "")}\033[0m to \033[{destcol}m{copydatdest.replace(args.dst_folder,"")}\033[0m')        
            
        if should_print:
            print()


myfile.close()
print(f' --- Completed {totalFileCount} Files in {(time.time() - start_time)} Seconds. {(time.time() - start_time)/totalFileCount} per file speed ---')