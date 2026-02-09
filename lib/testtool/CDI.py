import lib.logger as logger
import subprocess
import os
import json
import enum
import re
import shutil
import time

from pywinauto import Application
from pywinauto import keyboard
from pywinauto import findwindows
from pywinauto import timings
from pathlib import Path
import pyperclip
import psutil

class ReadMode(enum.Enum):
  start = 1
  cdiversion = 2
  controllermap = 3
  disklist = 4
  drivedata = 5
  smartdata = 6
  identifydata = 7
  smartreaddata = 8
  smartreadthreshold = 9


class CDI:

    def __init__(self):
        self.ExePath = './bin/CrystalDiskInfo/DiskInfo64.exe'
        self.LogPath = './testlog'
        self.LogPrefix = ""
        self.ScreenShotDriveLetter = ''
        self.file_rename = ''
        self.DiskInfo_txt_name = 'DiskInfo.txt'
        self.DiskInfo_json_name = 'DiskInfo.json'
        self.DiskInfo_png_name = ''
        return
    
    def SetConfigByPath(self,Path:str):
        with open(Path, newline='') as f:
            self.SetConfig(json.load(f))
        return

    def SetConfig(self,dictConfig:dict):
        for key,value in dictConfig.items():
            setattr(self,key,value)
        return

    def __Open__(self):
        
        absScriptPath = os.path.abspath(self.ExePath)
        self.app = Application(backend='win32').start(absScriptPath)
        self.windows = self.app.window(title_re=' CrystalDiskInfo ',class_name='#32770')
        self.windows.wait('ready', timeout=60)
        time.sleep(2)
        # self.windows.print_control_identifiers()
        return

    def __Connect__(self):
        self.app = Application(backend='win32').connect(title_re=' CrystalDiskInfo ',class_name='#32770')
        self.windows = self.app.window(title_re=' CrystalDiskInfo ',class_name='#32770')
        self.windows.wait('ready', timeout=60)
        return
    
    async def RunProcedure(self):
        self.__CreatDir__(self.LogPath)
        self.__Open__()
        self.__GetScreenShot__()
        self.__GetTextLog__()
        self.__Close__()
        return

    async def RunProcedureParserLog(self):
        self.kill_processes(['DiskInfo64.exe'])
        self.__CreatDir__(self.LogPath)
        self.__Open__()
        self.__GetTextLog__()
        self.__ParserLog__()
        self.__GetScreenShot__()
        self.__Close__()
        return

    def RunProcedureParserLog_sync(self):
        """
        Synchronous version of RunProcedureParserLog for pytest

        Execute CrystalDiskInfo monitoring and parse logs, fully synchronous.
        Suitable for use in the pytest test framework without async/await.

        Steps:
        1. Kill existing CDI processes
        2. Create the log directory
        3. Start CrystalDiskInfo
        4. Retrieve the text log
        5. Parse the log into JSON
        6. Capture screenshots
        7. Close the CDI window

        Returns:
            None (raises an exception on failure)
        """
        logger.LogEvt("[CDI-Sync] Start CrystalDiskInfo synchronous monitoring")
        
        # 1. Kill old processes
        logger.LogEvt("[CDI-Sync] Terminating old DiskInfo64.exe processes")
        self.kill_processes(['DiskInfo64.exe'])
        
        # 2. Create log directory
        logger.LogEvt(f"[CDI-Sync] Creating log directory: {self.LogPath}")
        self.__CreatDir__(self.LogPath)
        
        # 3. Start CrystalDiskInfo
        logger.LogEvt("[CDI-Sync] Starting CrystalDiskInfo")
        self.__Open__()
        
        # 4. Get text log
        logger.LogEvt("[CDI-Sync] Retrieving text log")
        self.__GetTextLog__()
        
        # 5. Parse log
        logger.LogEvt("[CDI-Sync] Parsing log to JSON")
        self.__ParserLog__()
        
        # 6. Screenshot
        if self.ScreenShotDriveLetter:
            logger.LogEvt(f"[CDI-Sync] Screenshotting drive {self.ScreenShotDriveLetter}")
            self.__GetScreenShot__()
        else:
            logger.LogEvt("[CDI-Sync] Skipping screenshot (ScreenShotDriveLetter not set)")
        
        # 7. Close window
        logger.LogEvt("[CDI-Sync] Closing CrystalDiskInfo")
        self.__Close__()
        
        logger.LogEvt("[CDI-Sync] CDI monitoring complete")
        return


    def __GetDiskInfo__(self):
        try:
            status = subprocess.call("{} /CopyExit".format(self.ExePath))

            absLogPath = os.path.abspath(self.ExePath)
            dirName = os.path.dirname(absLogPath)
            absTxtSourcePath = os.path.join(dirName,self.DiskInfo_txt_name)

            absLogPath = os.path.abspath(self.LogPath)
            absTxtTargetPath = os.path.join(absLogPath,"{}{}".format(self.LogPrefix,self.DiskInfo_txt_name))

            shutil.copy2(absTxtSourcePath,absTxtTargetPath)
        
        except WindowsError as e:
            if "Error 740" in str(e):
                logger.LogErr ("This application must be run as an administrator to get raw access to drives.")
                logger.LogErr ("Exiting.")
                os.path.exit(1)
            else:
                raise e

        if status != 0:
            raise Exception("DiskInfo.exe exited with status code "+status)

        return

    
    def __ParserLog__(self):
        # try:
        # self.__GetDiskInfo__()
        # absLogPath = os.path.abspath(self.LogPath)
        # absTxtTargetPath = os.path.join(absLogPath,"{}DiskInfo.txt".format(self.LogPrefix))

        absLogPath = os.path.abspath(self.ExePath)
        dirName = os.path.dirname(absLogPath)
        # absTxtSourcePath = os.path.join(dirName,"DiskInfo.txt")
        absTxtSourcePath = os.path.abspath( "{}/{}{}".format(self.LogPath,self.LogPrefix,self.DiskInfo_txt_name))
        # read data
        input_data = None

        with open(absTxtSourcePath, newline='') as f:
            input_data = f.read()

        # parse data
        obj = {"CDI": {}, "OS": {}, "controllers_disks": {}, "disks": []}
        curmode = ReadMode.start
        curdiskname = None
        curdiskidx = None
        curcontroller = None

        for linenum, line in enumerate(input_data.splitlines()):

            # skip blank lines
            if len(line) == 0:
                # print ("blank",line)
                continue

            # mode pivots
            # if re.search("^CrystalDiskInfo (\d*.\d*.\d*)",line):
            #     curmode = ReadMode.cdiversion
                # continue

            if re.search("^-- Controller Map",line):
                curmode = ReadMode.controllermap
                continue

            if re.search("^-- Disk List",line):
                curmode = ReadMode.disklist
                continue

            if re.search("^-- S.M.A.R.T. ",line):
                curmode = ReadMode.smartdata
                continue

            if re.search("^-- IDENTIFY_DEVICE ",line):
                curmode = ReadMode.identifydata
                continue

            if re.search("^-- SMART_READ_DATA ",line):
                curmode = ReadMode.smartreaddata
                continue

            if re.search("^-- SMART_READ_THRESHOLD ",line):
                curmode = ReadMode.smartreadthreshold
                continue

            result = re.search("^CrystalDiskInfo (\d*.\d*.\d*)",line)
            if result:
                ver = result.groups()[0]
                obj['CDI']['version'] = ver
                continue

            result = re.search("^    OS : (.*)$",line)
            if result:
                ver = result.groups()[0]
                obj['OS']['version'] = ver
                continue

            # if curmode == ReadMode.controllermap:
            #     if line.startswith(" + "):
            #         curcontroller = line[len(" + "):]
            #         obj["controllers_disks"][curcontroller] = []
            #     if line.startswith("   - "):
            #         obj["controllers_disks"][curcontroller].append(line[len("   - "):])
            #     continue

            if curmode == ReadMode.controllermap:
                if line.startswith(" + "):
                    cur_controller = line[len(" + "):]
                    obj["controllers_disks"][cur_controller] = []
                elif line.startswith("   - "):
                    if cur_controller not in obj:
                        obj["controllers_disks"][cur_controller] = []
                    obj["controllers_disks"][cur_controller].append(line[len("   - "):])
                continue

            if curmode == ReadMode.disklist:
                result = re.search("^ \((\d+)\) (.*) : (.*) \[(.*)/\d+/.*$",line)
                if result:
                    idx, name, size, phyid = result.groups()
                    obj['disks'].append({"DiskNum": idx, "Model": name, "Disk Size": size, "Physical Drive ID": phyid})

                elif line.startswith("-----------------"):
                    curmode = ReadMode.drivedata
                continue

            result = re.search("^ \((\d+)\) (.*)$",line)
            if result:
                curmode = ReadMode.drivedata
                curdiskidx, curdiskname = result.groups()
                continue

            if curmode == ReadMode.drivedata:
                splitstrip = [x.strip() for x in line.split(" : ")]
                if len(splitstrip) > 1:
                    attribute, value = splitstrip
                    obj['disks'][int(curdiskidx)-1][attribute] = value
                continue

            if curmode == ReadMode.smartdata:
                #SATA
                result = re.search("^([A-F0-9]{2}) _*(\d*) _*(\d*) _*(\d*) ([A-F0-9]{12}) (.*)$",line)
                if result:
                    _id, cur, wor, thr, rawvalues, attributename = result.groups()
                    smartobj = {"ID": _id, "Cur": cur, "Wor": wor, "Thr": thr, "RawValues": rawvalues, "Attribute Name": attributename}
                    # print(smartobj)
                    if "S.M.A.R.T." not in obj['disks'][int(curdiskidx)-1]:
                        obj['disks'][int(curdiskidx)-1]["S.M.A.R.T."] = []

                    obj['disks'][int(curdiskidx)-1]["S.M.A.R.T."].append(smartobj)

                
                # #NVMe
                result = re.search("^([A-F0-9]{2}) ([A-F0-9]{12}) (.*)$",line)
                if result:
                    _id, rawvalues, attributename = result.groups()
                    smartobj = {"ID": _id, "RawValues": rawvalues, "Attribute Name": attributename}
                    # logger.LogEvt(smartobj)
                    if "S.M.A.R.T." not in obj['disks'][int(curdiskidx)-1]:
                        obj['disks'][int(curdiskidx)-1]["S.M.A.R.T."] = []

                    obj['disks'][int(curdiskidx)-1]["S.M.A.R.T."].append(smartobj)

                continue

            if curmode == ReadMode.identifydata:
                # skip header
                if line.startswith("    "):
                    continue

                # extract hex, stripping off index at beginning
                hexdata = "".join(line.split(" ")[1:])

                # initialize on disk object if needed
                if "IDENTIFY_DEVICE" not in obj['disks'][int(curdiskidx)-1]:
                    obj['disks'][int(curdiskidx)-1]["IDENTIFY_DEVICE"] = ""

                obj['disks'][int(curdiskidx)-1]["IDENTIFY_DEVICE"] += hexdata
                continue

            if curmode == ReadMode.smartreaddata:
                # skip header
                if line.startswith("    "):
                    continue

                # extract hex, stripping off index at beginning
                hexdata = "".join(line.split(" ")[1:])

                # initialize on disk object if needed
                if "SMART_READ_DATA" not in obj['disks'][int(curdiskidx)-1]:
                    obj['disks'][int(curdiskidx)-1]["SMART_READ_DATA"] = ""

                obj['disks'][int(curdiskidx)-1]["SMART_READ_DATA"] += hexdata
                continue

            if curmode == ReadMode.smartreadthreshold:
                # skip header
                if line.startswith("    "):
                    continue

                # extract hex, stripping off index at beginning
                hexdata = "".join(line.split(" ")[1:])

                # initialize on disk object if needed
                if "SMART_READ_THRESHOLD" not in obj['disks'][int(curdiskidx)-1]:
                    obj['disks'][int(curdiskidx)-1]["SMART_READ_THRESHOLD"] = ""

                obj['disks'][int(curdiskidx)-1]["SMART_READ_THRESHOLD"] += hexdata
                continue
                # output data
        absLogPath = os.path.abspath(self.LogPath)
        absTxtTargetPath = os.path.join(absLogPath,"{}{}".format(self.LogPrefix,self.DiskInfo_json_name))
        with open(absTxtTargetPath, 'w') as f:
            f.write(json.dumps(obj, indent=4, separators=(",", ": "), sort_keys=True))
        return obj

    def __GetTextLog__(self):
        # self.__Connect__()
        absScriptPath = os.path.abspath(self.ExePath)


        retry_count = 0
        max_retry = 10

        while retry_count < max_retry:
            try:
                self.windows.set_focus()
                keyboard.send_keys('^T')
                saveApp = Application(backend='win32').connect(title='Save As', timeout=20)
                break
            except timings.TimeoutError:
                self.windows.set_focus()
                retry_count += 1

        else:
            raise Exception("Could not find the 'Save As' dialog")
        
        # keyboard.send_keys('^T')
        # saveApp = Application(backend='win32').connect(title='Save As', timeout= 30)
        saveWindows = saveApp.window(title='Save As',class_name='#32770')
        saveWindows.wait('ready', timeout=10)
        saveWindows.set_focus()
        # keyboard.send_keys('^a')
        # pyperclip.copy("")
        absName = os.path.abspath( "{}/{}{}".format(self.LogPath,self.LogPrefix,self.DiskInfo_txt_name))
        if os.path.exists(absName):
            os.remove(absName)
            time.sleep(2)
        # pyperclip.copy(os.path.join(absName))
        # keyboard.send_keys('^v')
        # self.windows.print_control_identifiers()

        max_retry = 10
        for retry_count in range(max_retry):
            if os.path.exists(absName):
                break
            if retry_count == max_retry - 1:
                raise Exception('Failed to save file after maximum retries')
            
            saveWindows.set_focus()
            ctrl = saveWindows['Edit']
            ctrl.set_text(absName)
            get_file_path = ctrl.window_text()
            logger.LogEvt(f'get_file_path={get_file_path}')
            saveWindows['&Save'].click()
            time.sleep(1)

        time.sleep(1)
        # keyboard.send_keys('{ENTER}')
        #self.__Close__()

        return

    
    def __GetScreenShot__(self):
        # self.__Connect__()
        absScriptPath = os.path.abspath(self.ExePath)
        #self.app = Application(backend='win32').start(absScriptPath)
        #self.windows = self.app.window(class_name='#32770')
        #self.windows.wait('ready', timeout=60)
        self.windows.set_focus()
        # self.windows.print_control_identifiers()
        # app_menu = self.app.top_window().menu()
        # diskMenu =  app_menu.get_menu_path("Disk")[0].sub_menu()
        app_menu_count = 0
        while True:
            try:
                app_menu_count += 1
                if app_menu_count == 10:
                    raise Exception("app_menu_count retry count = 10")
                time.sleep(2)
                app_menu = self.app.top_window().menu()
                diskMenu =  app_menu.get_menu_path("Disk")
                if diskMenu:
                    self.windows.set_focus()
                    diskMenu = diskMenu[0].sub_menu()
                    break
                # else:
                #     logger.LogEvt('Wait diskMenu={}'.format(diskMenu))
            except:
                
                # logger.LogEvt('app_menu={}'.format(app_menu))
                time.sleep(2)
                self.__Connect__()
                
        # iterate over the menu Items
        for item in diskMenu.items():
            if self.ScreenShotDriveLetter != '':
                Model = self.__GetDriveInfo__(self.ScreenShotDriveLetter,"",'Model')
                DiskNum = int(self.__GetDriveInfo__(self.ScreenShotDriveLetter,"",'DiskNum'))
                # print(f'Model={Model}')
                # print(f'str(item)={str(item)}')
                if Model in str(item) and f'({DiskNum})' in str(item):
                    logger.LogEvt(f'click={str(item)}')
                    item.select()
                else:
                    continue
            else:
                logger.LogEvt(f'click={str(item)}')
                item.select()


            time.sleep(1)

            retry_count = 0
            max_retry = 10
            while retry_count < max_retry:
                try:
                    retry_count += 1
                    self.windows.set_focus()
                    keyboard.send_keys('^S')
                    saveApp = Application(backend='win32').connect(title='Save As', timeout= 20)
                    break
                except timings.TimeoutError:
                    self.windows.set_focus()
                    retry_count += 1

            if retry_count == max_retry:
                raise Exception("UCould not find the 'Save As' dialog")

 
            # keyboard.send_keys('^S')
            # saveApp = Application(backend='win32').connect(title='Save As', timeout= 20)
            saveWindows = saveApp.window(title='Save As',class_name='#32770')
            saveWindows.wait('ready', timeout=10)
            time.sleep(1)
            saveWindows.set_focus()
            # keyboard.send_keys('%n')
            # keyboard.send_keys('^a')
            # pyperclip.copy("")
            #absName = os.path.abspath(self.LogPath + "/{}DiskInfo.png".format(self.LogPrefix))
            if self.DiskInfo_png_name != '':
                absName = os.path.abspath( "{}/{}{}".format(self.LogPath,self.LogPrefix,self.DiskInfo_png_name))
            else:
                # print(f'item.text()={item.text()}')
                item_text = item.text()
                if ':' in item_text:
                    item_text = item_text.replace(':', '')
                if ']' in item_text:
                    item_text = item_text.replace(']', '')
                if '[' in item_text:  
                    item_text = item_text.replace('[', '')
                absName = os.path.abspath( "{}/{}DiskInfo_{}.png".format(self.LogPath,self.LogPrefix,item_text))

            if os.path.exists(absName):
                os.remove(absName)
                time.sleep(2)
            # saveWindows.print_control_identifiers()
            # pyperclip.copy(os.path.join(absName))
            # saveWindows.print_control_identifiers(filename='c:\\log.log')

            retry_count = 0
            max_retry = 10
            while retry_count < max_retry:
                if not os.path.exists(absName):
                    saveWindows.set_focus()
                    ctrl = saveWindows['Edit']
                    ctrl.set_text(absName)
                    get_file_path = ctrl.window_text()
                    logger.LogEvt(f'get_file_path={get_file_path}')
                    # keyboard.send_keys('%n')
                    # keyboard.send_keys('^v')
                    saveWindows['&Save'].click()
                    retry_count += 1
                    time.sleep(1)
                elif os.path.exists(absName):
                    break
                time.sleep(1)

            if retry_count == max_retry:
                raise Exception("Unable to save file after {0} retries.".format(max_retry))
            # keyboard.send_keys('{ENTER}')
            #self.__Close__()
            time.sleep(3)

        return
    
    def __GetDriveInfo__(self, DriveLetter,LogPrefixName,key):
        '''SN = cdi.__GetDriveInfo__("C:","",'Serial Number')'''
        absLogPath = os.path.abspath(self.LogPath)
        absJsonTargetPath = os.path.join(absLogPath,"{}{}".format(LogPrefixName,self.DiskInfo_json_name))
        with open(absJsonTargetPath, newline='') as f:
            j = json.load(f)
            disk = j['disks']
            result = [x for x in disk if DriveLetter in x['Drive Letter'] ]
            if result:
                info = result[0][key]
        return info

    def __GetSmartValue__(self, DriveLetter,LogPrefixName,keys):
        absLogPath = os.path.abspath(self.LogPath)
        absJsonTargetPath = os.path.join(absLogPath,"{}{}".format(LogPrefixName,self.DiskInfo_json_name))
        tmplist = [] 
        with open(absJsonTargetPath, newline='') as f:
            j = json.load(f)
            # keys = ['Power Cycles', 'Power On Hours', 'Unsafe Shutdowns', 'Media and Data Integrity Errors', 'Power On Count']
            disk = j['disks']
            result = [x for x in disk if DriveLetter in x['Drive Letter']]
            if result:
                smart = result[0]['S.M.A.R.T.']
                tmpdict = {}
                for key in keys:
                    attribute = [x for x in smart if x['Attribute Name'] == key]
                    if attribute:
                        rawvalue = int(attribute[0]['RawValues'], 16)
                        # print('{} = {}'.format(key,rawvalue))
                        tmpdict.update({key:rawvalue})
                tmplist.append(tmpdict)
        return tmplist

    def __CompareSmartValue__(self,DriveLetter, LogPrefixName,keys, smartvalue):
        # CompareSmartValue
        '''
        cdi.DiskInfo_json_name = 'CDI_before.json'
        keys = ['Number of Error Information Log Entries', 'Media and Data Integrity Errors']
        result,msg   = cdi.__CompareSmartValue__('C:', '', keys, 0)
        result,msg = cdi.__CompareSmartValue__('C:', 'Before_', keys, 0)
        if not result:
            raise Exception(msg)

        '''
        result = False
        msg = ''
        value = self.__GetSmartValue__(DriveLetter,LogPrefixName,keys)
        for key in keys:
            GetValue = value[0][key]

            if GetValue != smartvalue:
                msg = 'Check SMART Failed {} : {} != {}'.format(key, GetValue,smartvalue)
                logger.LogErr(msg)
                return False,msg
            else:
                msg = 'Check SMART Passed {} : {} == {}'.format(key, GetValue,smartvalue)
                logger.LogEvt(msg)
        return True,msg

    def __CompareSmartValueNoIncrease__(self,DriveLetter, BeforeLogPrefixName, AfterLogPrefixName,keys):
        # noincrease
        '''
        keys = ['Unsafe Shutdowns', 'Power Cycles']
        cdi.DiskInfo_json_name = '.json'
        result,msg = cdi.__CompareSmartValueNoIncrease__('C:', 'CDI_before', 'CDI_after', keys)
        result,msg = cdi.__CompareSmartValueNoIncrease__('C:', 'Before_', 'After_', keys)
        if not result:
            raise Exception(msg)
        '''
        result = False
        msg = ''
        before = self.__GetSmartValue__(DriveLetter,BeforeLogPrefixName,keys)
        after  = self.__GetSmartValue__(DriveLetter,AfterLogPrefixName,keys)
        for key in keys:
            BFValue = before[0][key]
            AFValue  = after[0][key]
            if BFValue != AFValue:
                msg = 'Check SMART Failed {} : {} != {}'.format(key, BFValue,AFValue)
                logger.LogErr(msg)
                return False,msg
            else:
                msg = 'Check SMART Passed {} : {} == {}'.format(key, BFValue,AFValue)
                logger.LogEvt(msg)
        return True,msg


    def __CompareSmartValueIncrease__(self,DriveLetter, BeforeLogPrefixName, AfterLogPrefixName, smartcount, keys):
        # increase
        # keys = ['Power Cycles']
        # result,msg = cdi.__CompareSmartValueIncrease__('C:', 'Before_', 'After_', 13, keys)
        # if not result:
        #     raise Exception(msg)
        '''
        keys = ['Power Cycles']
        cdi.DiskInfo_json_name = '.json'
        result,msg = cdi.__CompareSmartValueIncrease__('C:', 'CDI_before', 'CDI_after', 13, keys)
        result,msg = cdi.__CompareSmartValueIncrease__('C:', 'Before_', 'After_', 13, keys)
        if not result:
            raise Exception(msg)
        '''
        result = False
        msg = ''
        before = self.__GetSmartValue__(DriveLetter,BeforeLogPrefixName,keys)
        after  = self.__GetSmartValue__(DriveLetter,AfterLogPrefixName,keys)
        for key in keys:
            BFValue = before[0][key]
            AFValue  = after[0][key]
            if (AFValue - BFValue) != smartcount:
                msg = 'Check SMART Failed {} : {} - {} != {}'.format(key, AFValue,BFValue, smartcount)
                logger.LogErr(msg)
                return False,msg
            else:
                msg = 'Check SMART Passed {} : {} - {} == {}'.format(key, AFValue,BFValue, smartcount)
                logger.LogEvt(msg)

        return True,msg
        
    def __CreatDir__(Self,Dir):
        if not os.path.exists(Dir):
            Path(Dir).mkdir(parents=True, exist_ok=True)
        return

    def kill_processes(self,process_name):
        # process_names = ["fio.exe", "bit.exe"]

        for proc in psutil.process_iter(['name']):
            if proc.info['name'] in process_name:
                logger.LogEvt(f"taskkill {proc.info['name']}")
                subprocess.call(['taskkill', '/F', '/IM', proc.info['name']])

    def __Close__(self):
        time.sleep(2)
        self.app.kill()
        return