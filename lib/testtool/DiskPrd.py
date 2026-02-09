from asyncio import subprocess
import sys
import os

sys.path.append(os.path.dirname(__file__))
# import SmiCli  # Moved to lazy import in functions that need it
import os
import subprocess
import json
import logging
import win32api
from pathlib import Path
import lib.testtool.DiskUtility as DiskUtility


def ShrinkAndFormatDisk():
    ConfigPath = os.path.abspath('./Config/Config.json')
    logging.info('PartitionDiskByConfig. Path:' + ConfigPath)
    with open(ConfigPath, newline='') as f:
        j = json.load(f)
    logging.info('PartitionDiskByConfig. json:' + json.dumps(j))
    for config in j['DiskPartition']['PartList']:
        logging.info(config)
        if 'ShrinkLabel' in config:
            ShrinkDisk(config['ShrinkLabel'], config['Capacity'])
        FormatDisk(config['DiskID'], config['Format'], config['Label'], config['Capacity'], config['Unit'])


def ShrinkDisk(disk_part, size):
    try:
        cmd = ['select volume=%s' % disk_part, 'shrink desired=%s' % size]
        WriteTmpFileAndExcute(cmd)
    except Exception as e:
        print("ShrinkDisk Exception:" + str(e))
        return 0


def FormatDisk(disk_id, fs, label, size, unit):
    try:
        cmd = [
            "select disk %s" % disk_id,
            f"create partition primary" + (f" size={size}" if size is not None else ""),
            f"format fs={fs} unit={unit} quick" if unit is not None else f"format fs={fs} quick",
            "assign letter=%s" % label]
        WriteTmpFileAndExcute(cmd)
    except Exception as e:
        print("FormatDisk Exception:" + str(e))
        return 0


def RestoreDiskPart():
    try:
        extend_vol = []
        ConfigPath = os.path.abspath('./Config/Config.json')
        logging.info('RestoreDiskPart By Config. Path:' + ConfigPath)
        with open(ConfigPath, newline='') as f:
            j = json.load(f)
        logging.info('PartitionDiskByConfig. json:' + json.dumps(j))
        for config in j['DiskPartition']['PartList']:
            logging.info(config)
            logging.info('Delete Volume %s' % config['Label'])
            DeleteVolume(config['Label'])
            if 'ShrinkLabel' in config:
                if config['ShrinkLabel'] not in extend_vol:
                    extend_vol.append(config['ShrinkLabel'])

        for vol in extend_vol:
            cmd = [
                "select volume %s" % vol,
                "extend"
            ]
            logging.info('Extend Volume %s' % vol)
            WriteTmpFileAndExcute(cmd)
    except Exception as e:
        print("RestoreDiskPart Exception:" + str(e))
        return 0


def GetDiskInfo():
    disk_info = {}
    disk_ret = ExecuteDiskPartCmd(['list disk'])
    for n in disk_ret:
        if n.startswith("  Disk ") and not n.startswith("  Disk ###"):
            cmd = [
                'select disk %s' % n.split()[1],
                'detail disk'
            ]
            vol_ret = ExecuteDiskPartCmd(cmd)
            vol_list = []
            for v in vol_ret:
                if v.startswith("  Volume ") and not v.startswith("  Volume ###"):
                    if len(v.split()[2]) == 1:
                        vol_list.append(v.split()[2])
            disk_info[n.split()[1]] = vol_list
    # {'0': ['C', 'D'], '1': ['E', 'F', 'G']}
    return disk_info


def ExecuteDiskPartCmd(cmd):
    tempFile = os.path.abspath(".\python-diskpart.txt")
    if os.path.exists(tempFile):    os.remove(tempFile)
    logging.info("DiskPartCmds:" + str(cmd))
    with open(tempFile, 'w') as f:
        for c in cmd:
            f.write("%s\n" % c)
    logging.info("Excute Path:" + str(tempFile))
    ret = subprocess.check_output(["diskpart", "/s", tempFile], shell=True)
    ret_str = []
    for n in ret.splitlines():
        ret_str.append(str(n, 'utf-8'))
    return ret_str


def CleanDiskPart():
    try:
        # get to use disk
        use_disk_list = []
        ConfigPath = os.path.abspath('./Config/Config.json')
        logging.info('PartitionDiskByConfig. Path:' + ConfigPath)
        with open(ConfigPath, newline='') as f:
            j = json.load(f)
        logging.info('PartitionDiskByConfig. json:' + json.dumps(j))
        for config in j['DiskPartition']['PartList']:
            if str(config['DiskID']) not in use_disk_list:
                use_disk_list.append(str(config['DiskID']))

        disk_info = GetDiskInfo()

        for d in use_disk_list:
            if "C" in disk_info[d]:
                # primary disk
                for label in disk_info[d]:
                    if label != 'C':
                        DeleteVolume(label)
                cmd = [
                    "select volume C",
                    "extend"
                ]
                ExecuteDiskPartCmd(cmd)
            else:
                # secondary disk
                cmd = [
                    "select disk %s" % d,
                    "clean",
                    "convert gpt"
                ]
                ExecuteDiskPartCmd(cmd)
    except Exception as e:
        print("CleanDiskPart Exception:" + str(e))
        return 0


def DeleteInUseVolume():
    disk_info = GetDiskInfo()
    # get to use label exclude C
    to_use_label_list = []
    ConfigPath = os.path.abspath('./Config/Config.json')
    logging.info('PartitionDiskByConfig. Path:' + ConfigPath)
    with open(ConfigPath, newline='') as f:
        j = json.load(f)
    logging.info('PartitionDiskByConfig. json:' + json.dumps(j))
    for config in j['DiskPartition']['PartList']:
        if config['Label'] not in to_use_label_list and config['Label'] != "C":
            to_use_label_list.append(config['Label'])

    for disk_id, label in disk_info.items():
        for dl in label:
            if dl in to_use_label_list and dl != 'C':
                # if in use try to remove
                DeleteVolume(dl)
                # extend C because un-allocate space in primary disk
                if 'C' in label and len(label) > 1:
                    cmd = [
                        "select volume C",
                        "extend"
                    ]
                    ExecuteDiskPartCmd(cmd)


def DeleteVolume(label):
    try:
        # get list
        diskpart_cmds = ['list volume']
        tempFile = os.path.abspath(".\python-diskpart.txt")
        print(tempFile)
        if os.path.exists(tempFile):
            os.remove(tempFile)
        logging.info("DiskPartCmds:" + str(diskpart_cmds))
        with open(tempFile, 'w') as f:
            for cmd in diskpart_cmds:
                f.write("%s\n" % cmd)
        logging.info("Excute Path:" + str(tempFile))
        ret = subprocess.check_output(["diskpart", "/s", tempFile], shell=True)

        for n in ret.splitlines():
            str_n = str(n, 'utf-8')
            if str_n.startswith("  Volume") and not str_n.startswith("  Volume ###"):
                if label == str_n.split()[2]:
                    cmd = [
                        "select volume %s" % str_n.split()[1],
                        "delete volume override"
                    ]
                    WriteTmpFileAndExcute(cmd)
                    break

    except Exception as e:
        print("DeleteVolume Exception:" + str(e))
        return 0


def PartitionDiskByConfig(ConfigPath):
    logging.info('PartitionDiskByConfig. Path:' + ConfigPath)
    with open(ConfigPath, newline='') as f:
        j = json.load(f)
    logging.info('PartitionDiskByConfig. json:' + json.dumps(j))
    PartitionDisk(j['DiskSetting'])
    return


def PartitionDisk(DiskConfig):
    import SmiCli  # Lazy import
    PrimaryTask = []
    SecondaryTask = []
    DiskPartCmds = []
    smiCli = SmiCli.SmiCli()
    diskInfo = smiCli.GetDriveInfo()
    if (diskInfo):
        for diskconfig in DiskConfig:
            result = CheckDiskType(diskconfig['DiskID'], diskInfo['json']['drive_info_list'])
            if result == 1:
                PrimaryTask.append(diskconfig)
            elif result == 2:
                SecondaryTask.append(diskconfig)

        DiskPartCmds.extend(HandlePrimary(PrimaryTask, diskInfo['json']['drive_info_list']))
        DiskPartCmds.extend(HandlePrimary(SecondaryTask, diskInfo['json']['drive_info_list']))
        WriteTmpFileAndExcute(DiskPartCmds)
    return


def WriteTmpFileAndExcute(DiskPartCmds):
    tempFile = os.path.abspath(".\python-diskpart.txt")
    print(tempFile)
    if os.path.exists(tempFile):    os.remove(tempFile)
    logging.info("DiskPartCmds:" + str(DiskPartCmds))
    with open(tempFile, 'w') as f:
        for cmd in DiskPartCmds:
            f.write("%s\n" % cmd)
    logging.info("Excute Path:" + str(tempFile))
    subprocess.call(["diskpart", "/s", tempFile], shell=True)
    return


def HandlePrimary(PrimaryTask, DriveInfo):
    cmdList = []

    for task in PrimaryTask:
        for part in task['PartList']:
            if not GetDiskIDByLabel(part['Label'], DriveInfo) != -1:
                cmdPattern = [
                    "select volume=c",
                    "shrink desired=" + str(part['Capacity']),
                    "create partition primary size=" + str(part['Capacity']),
                    "format fs=" + part['Format'] + " unit=" + part['Unit'] + " quick",
                    "assign letter=" + part['Label']
                ]
                cmdList.extend(cmdPattern)
            else:  # skip if partition existed
                continue

    return cmdList


def HandleSecondary(SecondaryTask):
    print('SecondaryTask')
    return []


def CheckDiskType(DiskNo, DriveInfo):
    try:
        diskInfoList = []
        [diskInfoList.extend(x['disk_info_list']) for x in DriveInfo]
        for disk in diskInfoList:
            partList = disk['part_info_list']
            if disk['id'] == DiskNo:
                tmpResult = [x for x in partList if x['drive_letter'] == 'C']
                if (len(tmpResult)):
                    return 1
                else:
                    return 2

        return -1
    except Exception as e:
        print("CheckIsPrimary() Exceptio:" + str(e))
        return 0


def GetDiskIDByLabel(Label, DriskInfo):
    try:
        diskInfoList = []
        [diskInfoList.extend(x['disk_info_list']) for x in DriskInfo]
        for disk in diskInfoList:
            partList = disk['part_info_list']
            tmpResult = len([x for x in partList if x['drive_letter'] == Label])
            if (tmpResult > 0):
                return disk['id']
        return -1
    except Exception as e:
        print("CheckVolumeExisted() Exceptio:" + str(e))
        return False


def GetDiskIDByTypeID(TypeID):
    import SmiCli  # Lazy import
    # 320 = NVMe
    smicli = SmiCli.SmiCli()
    # dut_infoPath = smicli.LogPath + '/Dut_Info.json'
    # if os.path.exists(dut_infoPath):    os.remove(dut_infoPath)
    diskInfo = smicli.GetDriveInfo()['json']
    try:
        idList = []
        data = diskInfo['drive_info_list']
        drives = [x['disk_info_list'] for x in data if x['disk_type'] == TypeID]
        for drive in drives:
            for disk in drive:
                if disk['id'] not in idList:
                    idList.append(disk['id'])
        return idList
    except Exception as e:
        print("GetDiskIDByTypeID() Exceptio:" + str(e))
        return False


def RemoveDiskLabel(Label):
    drives = win32api.GetLogicalDriveStrings()
    drives = drives.split('\000')[:-1]

    for drive in drives:
        if Label in drive:
            cmdList = []
            cmdPattern = [
                "list disk",
                "sel vol {}".format(Label),
                "remove letter {}".format(Label)
            ]
            cmdList.extend(cmdPattern)
            WriteTmpFileAndExcute(cmdList)
    return


def CleanDiskCreateLabel(DiskId, Label):
    RemoveDiskLabel(Label)

    cmdList = []
    cmdPattern = [
        "list disk",
        "sel disk {}".format(DiskId),
        "clean",
        "create part pri",
        "format fs=NTFS Quick",
        "assign letter {}:".format(Label)
    ]
    cmdList.extend(cmdPattern)
    # print('cmdList=', cmdList)
    WriteTmpFileAndExcute(cmdList)
    return


def CleanDisk(DiskId):
    cmdList = []
    cmdPattern = [
        "list disk",
        "sel disk {}".format(DiskId),
        "clean"
    ]
    cmdList.extend(cmdPattern)
    # print('cmdList=', cmdList)
    WriteTmpFileAndExcute(cmdList)
    return

def DelVolume(VolId):
    # DelVolume("D")
    cmdList = []
    cmdPattern = [
        "sel Vol {}".format(VolId),
        "del vol override"
    ]
    cmdList.extend(cmdPattern)
    # print('cmdList=', cmdList)
    WriteTmpFileAndExcute(cmdList)
    return

def ExtendVolume(VolId):
    # ExtendVolume("C")
    cmdList = []
    cmdPattern = [
        "sel Volume {}".format(VolId),
        "extend"
    ]
    cmdList.extend(cmdPattern)
    # print('cmdList=', cmdList)
    WriteTmpFileAndExcute(cmdList)
    return