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
args = parser.parse_args()
src_folder = os.path.join(args.src_folder, '')
dst_name = datetime.datetime.now().strftime(f"_%Y-%m-%d_%H.%M.%S")
dst_folder = os.path.join(args.dst_folder, '') + args.src_folder.split(os.sep)[-1] + dst_name + os.sep

#make sure the destination folder exists
os.system(f"cp '{src_folder}' '{dst_folder}' -p -r --sparse=always -a")  

#recursively itterate over the source folder
def copyData(copydatsource, copydatdest):
    print(f'---- copy data from \033[34m{copydatsource}\033[0m to \033[35m{copydatdest}\033[0m ----')
    
    #get source stats
    timesList = [x[:-28].split(":") for x in list(filter(lambda x: 'time' in x, subprocess.run(["debugfs", "-R", f'stat <{os.stat(copydatsource).st_ino}>', args.dev_path], capture_output=True, text=True).stdout.split("\n")))]
    
    #copy over the inode fields
    for time in timesList:
        #copy the change (ctime), access (atime), modify (mtime), birth time (crtime)
        subprocess.run(["debugfs", "-w", "-R", f'set_inode_field <{os.stat(copydatdest).st_ino}> {time[0].strip()} @{time[1].strip()}', args.dev_path], capture_output=True)
        subprocess.run(["debugfs", "-w", "-R", f'set_inode_field <{os.stat(copydatdest).st_ino}> {time[0].strip()}_extra 0x{time[2].strip()}', args.dev_path], capture_output=True)    
        
    
    #get dest stats
    destTimesList = [x[:-28].split(":") for x in list(filter(lambda x: 'time' in x, subprocess.run(["debugfs", "-R", f'stat <{os.stat(copydatdest).st_ino}>', args.dev_path], capture_output=True, text=True).stdout.split("\n")))]
    print(f'\033[34m{timesList}\033[0m')
    if timesList == destTimesList:
        print(f'\033[32m{destTimesList}\033[0m')
    else:
        #deststattext = subprocess.run(["debugfs", "-R", f'stat <{os.stat(copydatdest).st_ino}>', args.dev_path], capture_output=True, text=True)
        #print(f'\033[32m{deststattext}\033[0m')
        os.system('sudo sync && sudo sysctl -w vm.drop_caches=3')
        print(f'\033[34m{str(subprocess.run(["stat", f"{copydatsource}"], capture_output=True, text=True).stdout)}\033[0m')
        print(f'\033[35m{str(subprocess.run(["stat", f"{copydatdest}"], capture_output=True, text=True).stdout)}\033[0m')
        print(f'\033[31mTRY AGAIN\033[0m')
    

for root, dirs, files in os.walk(src_folder):    
    #print(f'\033[4;1;34m{root}\033[0m')
    copyData(root, root.replace(src_folder, dst_folder))
    for file in files:
        sourceFilePath = os.path.join(root, '') + file
        copyData(sourceFilePath, sourceFilePath.replace(src_folder, dst_folder))