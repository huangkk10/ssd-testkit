import lib.logger as logger
from asyncio import subprocess
import os
from shutil import copy2
import asyncio
import time
import subprocess
import pathlib
from pywinauto import Application
import json
from pathlib import Path
import re
from pywinauto import ElementNotFoundError
from pywinauto import findwindows, timings
import getpass
import pyautogui
import psutil
import _ctypes
import win32api

class BurnIn:

    def __init__(self):
        self.username = getpass.getuser()
        self.Path = './bin/BurnIn/bit.exe'
        self.ScriptPath = './Config/BurnInScript.bits'
        self.CfgFilePath = './Config/DT_1D.BITCFG'
        self.TestTime = ''
        self.LogPath = './testlog/BurnIn.log'
        self.LogPrefix = ""
        self.timeout = 1
        self.Installer = None
        self.InstallPath = None
        self.LicensePath = None
        self.break_signal = False
        self.status = None
        self.Installer_name = None
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
        absScriptPath = os.path.abspath(self.ScriptPath)
        burnInPath = pathlib.Path(self.Path).parent.resolve()
        LastUsedPath = f'C:\\Users\\{self.username}\\Documents\\PassMark\\BurnInTest\\Configs'
        CfgFileName = os.path.basename(self.CfgFilePath)

        # print(os.path.join(burnInPath,"Configs",CfgFileName))
        # print(os.path.join(burnInPath,CfgFileName))
        if not os.path.exists(os.path.join(burnInPath,"Configs")):
            Path(os.path.join(burnInPath,"Configs")).mkdir(parents=True, exist_ok=True)
        if not os.path.exists(os.path.join(LastUsedPath)):
            Path(os.path.join(LastUsedPath)).mkdir(parents=True, exist_ok=True)
        copy2(self.CfgFilePath,os.path.join(burnInPath,"Configs",CfgFileName))
        copy2(self.CfgFilePath,os.path.join(burnInPath,CfgFileName))
        copy2(self.CfgFilePath,os.path.join(LastUsedPath,"Last Used.bitcfg"))
        
        #absCfgPath = os.path.abspath(self.CfgPath)
        # self.Process = subprocess.Popen([self.Path,"-C",CfgFileName,"-S",absScriptPath,"-K","-R"])
        self.Process = subprocess.Popen([self.Path,"-S",absScriptPath,"-K","-R"])
        self.__Connect__()
        # self.App =  Application(backend="uia").connect(title_re=u'BurnInTest', timeout=180)
        # # self.App =  Application(backend="uia").connect(process=self.Process.pid, timeout=180)
        # self.Windows = self.App.window(title_re=u'BurnInTest', class_name='bit')
        # self.Windows.wait('ready', timeout=180)
        # time.sleep(5)
        # self.Windows.print_control_identifiers()
        
        # DialogOK = self.Windows.child_window(title="OK", auto_id="1", control_type="Button")
        # DialogOK.print_control_identifiers()
        
        # while True:
        #     DialogOK = self.Windows.child_window(title="OK", auto_id="1", control_type="Button")
        #     try:
        #         DialogOK.wait_not('ready', timeout=2)
        #     except Exception:
        #         DialogOK.set_focus()
        #         DialogOK.click()
        #         break
            # time.sleep(1)

        # while True:
        #     if DialogOK.exists(timeout=20):
        #         DialogOK.set_focus()
        #         DialogOK.click()
        #         time.sleep(1)
        #     else:
        #         break
        #     time.sleep(1)
        #self.App = Application(backend="uia").connect(title_re='BurnInTest')
        # time.sleep(5)
        # self.Windows.print_control_identifiers()
        return


    def __RunScript__(self,cmd):
        # cmd = ["-S",os.path.abspath(self.ScriptPath),'-K', '-R', '-W']
        absScriptPath = os.path.abspath(self.ScriptPath)
        burnInPath = pathlib.Path(self.Path).parent.resolve()
        LastUsedPath = f'C:\\Users\\{self.username}\\Documents\\PassMark\\BurnInTest\\Configs'
        CfgFileName = os.path.basename(self.CfgFilePath)

        # logger.LogEvt(os.path.join(burnInPath,"Configs",CfgFileName))
        # logger.LogEvt(os.path.join(burnInPath,CfgFileName))
        # logger.LogEvt(os.path.join(burnInPath,"Configs"))
        # logger.LogEvt(os.path.join(LastUsedPath))
        if not os.path.exists(os.path.join(burnInPath,"Configs")):
            Path(os.path.join(burnInPath,"Configs")).mkdir(parents=True, exist_ok=True)
        if not os.path.exists(os.path.join(LastUsedPath)):
            Path(os.path.join(LastUsedPath)).mkdir(parents=True, exist_ok=True)
        copy2(self.CfgFilePath,os.path.join(burnInPath,"Configs",CfgFileName))
        copy2(self.CfgFilePath,os.path.join(burnInPath,CfgFileName))
        copy2(self.CfgFilePath,os.path.join(LastUsedPath,"Last Used.bitcfg"))

        self.Process = subprocess.Popen([self.Path] + cmd)
        self.__Connect__()
        # self.App =  Application(backend="uia").connect(process=self.Process.pid, timeout=60)
        # self.Windows = self.App.window(class_name='bit')
        # self.Windows.wait('ready', timeout=60)
        return
    
    def __Connect__(self):
        # self.App = Application(backend="uia").connect(title_re='BurnInTest',timeout=180,found_index=0)
        # self.Windows = self.App.window(title_re=u'BurnInTest', class_name='bit')
        timings.window_find_timeout = 180
        retry_count = 0
        retry_max_count = 60
        process_id = None
        while True:
            retry_count += 1
            for process in psutil.process_iter(['pid', 'name']):
                if process.info['name'] == 'bit.exe':
                    process_id = process.info['pid']
                    break
            if process_id != None:
                logger.LogEvt(f'bit.exe : process_id = {process_id} ')
                break
            if  retry_count > retry_max_count:
                raise Exception(f'BurnIn Connect Process Id Failed, retry_count = {retry_count} > retry_max_count = {retry_max_count}')

        retry_count = 0
        retry_max_count = 60
        while True:
            try:
                logger.LogEvt(f'Attempting to connect to BurnInTest window (retry {retry_count}/{retry_max_count})...')
                self.App = Application(backend="uia").connect(title_re='BurnInTest', process=process_id, timeout=180)
                # self.App = Application(backend="uia").connect(title_re='BurnInTest',timeout=180,found_index=0)
                self.Windows = self.App.top_window()
                # self.window.print_control_identifiers()
                logger.LogEvt(f'Connected to window, waiting for ready state...')
                self.Windows.wait('ready', timeout=timings.window_find_timeout)
                logger.LogEvt(f'BurnIn Connect successfully.')
                break
            except Exception as e:
                retry_count += 1
                logger.LogErr(f'BurnIn Connect failed (attempt {retry_count}/{retry_max_count}): {str(e)}')
                if retry_count > retry_max_count:
                    logger.LogErr(f'BurnIn Connect failed after {retry_max_count} retries')
                    raise Exception(f'BurnIn Connect Failed after {retry_max_count} retries. Last error: {str(e)}')
                time.sleep(3)
                logger.LogEvt(f'BurnIn Connect error : {str(e)}')
                retry_count += 1
                if  retry_count > retry_max_count:
                    raise Exception(f'BurnIn Connect Failed, retry_count = {retry_count} > retry_max_count = {retry_max_count}')
        return

    async def WaitTestDone(self):
            diaBoxOK = self.Windows.child_window(title="OK", auto_id="1", control_type="Button",found_index=0)
            diaIncorrectFileBtn = self.App.window(title='Incorrect file').child_window(control_type="Button", auto_id="2",found_index=0)
            statusImage = self.Windows.child_window(auto_id="14004", control_type="Image")
            time.sleep(5)
            while True:
                if diaBoxOK.exists(timeout=1):
                    diaBoxOK.click()
                if diaIncorrectFileBtn.exists(timeout=1):
                    diaIncorrectFileBtn.click()
                if statusImage.exists(timeout=1):
                    testStatus = statusImage.texts()[0].upper().replace(" ","")
                    if "RUNNING" in testStatus or "STARTING" in testStatus :
                        r = re.search("\((\d+)ERRORS\)",testStatus)
                        if r:
                            # print(r.group(1))
                            if int(r.group(1)) > 0:
                                print("ERROR DURING RUNNING ,Test Fail")
                                #os.system("pause")
                                return False,"'"+testStatus+"'"
                    elif "TESTSPASSED"   in testStatus :
                        return True,"'"+testStatus+"'"
                    else:
                        return False,"'"+testStatus+"'"
                    
                await asyncio.sleep(2)

    async def CheckErrorSatus(self):
            self.__Connect__()
            statusImage = self.Windows.child_window(auto_id="14004", control_type="Image")
            while True:
                try:
                    if statusImage.exists(timeout=self.timeout):
                        testStatus = statusImage.texts()[0].upper().replace(" ","")
                        if "RUNNING" in testStatus or "STARTING" in testStatus or "PASSED" in testStatus:
                            r = re.search("\((\d+)ERRORS\)",testStatus)
                            if r:
                                print(r.group(1))
                                if int(r.group(1)) > 0:
                                    print("ERROR DURING RUNNING ,Test Fail")
                                    #os.system("pause")
                                    return False,"'"+testStatus+"'"
                            # return True,"NoError"
                        else:
                            return False,"'"+testStatus+"'"
                    await asyncio.sleep(2)
                except findwindows.ElementNotFoundError as e:
                    logger.LogEvt(f'findwindows.ElementNotFoundError:{str(e)}')
                    await asyncio.sleep(2)
                    pass

                except _ctypes.COMError as com_error:
                    logger.LogEvt(f"Caught a COMError: {str(com_error)}" )
                    await asyncio.sleep(2)
                    pass


    def __SetConfig__(self):

        return

    def __SetBurnInScript__(self):
        absLogPath = os.path.abspath(self.LogPath)
        absfgFilePath = os.path.abspath(self.CfgFilePath)
        if self.TestTime == '':
            cmdStr = """
LOAD "{}"
SETLOG LOG yes Name "{}" TIME no REPORT text
RUN CONFIG
        """.format(absfgFilePath, absLogPath)
        else:
            cmdStr = """
LOAD "{}"
SETLOG LOG yes Name "{}" TIME no REPORT text
SETDURATION {}
RUN CONFIG
        """.format(absfgFilePath, absLogPath,self.TestTime)  

        with open(self.ScriptPath, "w") as bat_file:
            bat_file.write(cmdStr)
        print(cmdStr)
        return

    def generate_burnin_test_script(self,cmdStr):
        '''https://blog.csdn.net/Johnny_Haisheng/article/details/88187092

        LOAD "{os.path.abspath(burnin.CfgFilePath)}" 
        SETLOG LOG yes Name "{os.path.abspath(burnin.LogPath)}" TIME no REPORT text
        SETDURATION 1
        SETDISK DISK D:
        RUN DISK
        '''

        with open(self.ScriptPath, "w") as bat_file:
            bat_file.write(cmdStr)
        logger.LogEvt(f'generate_burnin_test_script : \n{cmdStr}')
        return




    def __SaveLog__(self):

        return


    def __Stop__(self):
        self.__Connect__()
        ctrl = self.Windows.child_window(auto_id="13000", control_type="Button").click()
        # self.window.print_control_identifiers()
        return

    def __Close__(self):
        self.App.kill()
        return
                
    
    async def RunProcedure(self):
        self.__Open__()
        resultFlat,Msg = await self.WaitTestDone()
        if not resultFlat:
            raise Exception('BurnIn Failed. Test Status:'+str(Msg))
        self.__Close__()
        
        return


    async def RunScriptProcedure(self,cmd):
        self.__RunScript__(cmd)
        resultFlat,Msg = await self.CheckTestSatus()
        if not resultFlat:
            raise Exception('BurnIn Failed. Test Status:'+str(Msg))
        # self.__Close__()
        
        return

    ##
    def install(self):
        # check InstallPath and key exist
        exe = os.path.join(self.InstallPath,'bit.exe')
        print(exe)
        if os.path.exists(exe):
            logger.LogEvt('BurnIn has been installed')
        else:
            cmd = '%s /SILENT /DIR="%s"' % (self.Installer,self.InstallPath)
            ret = subprocess.run(cmd)
            if ret.returncode:
                raise Exception('BurnIn install Failed!')

        if os.path.exists(os.path.join(self.InstallPath, 'key.dat')):
            logger.LogEvt('BurnIn key has been copied')
        else:
            copy2(os.path.abspath(self.LicensePath),self.InstallPath)

        self.SetConfig({'Path': exe})

    def uninstall(self):
        """
        Uninstall BurnIN test tool
        
        Steps:
        1. Check if BurnIN is installed
        2. Kill any running BurnIN processes
        3. Run uninstaller
        4. Clean up installation directory if needed
        """
        try:
            # Check if BurnIN is installed
            exe = os.path.join(self.InstallPath, 'bit.exe')
            uninstaller = os.path.join(self.InstallPath, 'unins000.exe')
            
            if not os.path.exists(self.InstallPath):
                logger.LogEvt('BurnIN is not installed (directory does not exist)')
                return True
            
            if not os.path.exists(exe):
                logger.LogEvt('BurnIN is not installed (executable not found)')
                return True
            
            logger.LogEvt(f'Starting BurnIN uninstallation from: {self.InstallPath}')
            
            # Step 1: Kill any running BurnIN processes
            self._kill_burnin_processes()
            
            # Step 2: Run uninstaller if exists
            if os.path.exists(uninstaller):
                logger.LogEvt(f'Running uninstaller: {uninstaller}')
                cmd = f'"{uninstaller}" /SILENT'
                ret = subprocess.run(cmd, shell=True, timeout=60)
                
                # Wait for uninstaller to complete
                time.sleep(5)
                
                if ret.returncode != 0:
                    logger.LogErr(f'Uninstaller returned code: {ret.returncode}')
            else:
                logger.LogEvt('Uninstaller not found, will remove directory manually')
            
            # Step 3: Force remove installation directory if still exists
            if os.path.exists(self.InstallPath):
                logger.LogEvt(f'Removing installation directory: {self.InstallPath}')
                import shutil
                try:
                    shutil.rmtree(self.InstallPath, ignore_errors=True)
                    logger.LogEvt('Installation directory removed successfully')
                except Exception as e:
                    logger.LogErr(f'Failed to remove directory: {e}')
            
            logger.LogEvt('BurnIN uninstallation completed')
            return True
            
        except Exception as e:
            logger.LogErr(f'BurnIN uninstall failed: {e}')
            return False
    
    def _kill_burnin_processes(self):
        """Kill all running BurnIN processes"""
        try:
            process_names = ['bit.exe', 'bit64.exe']
            killed_count = 0
            
            for proc in psutil.process_iter(['pid', 'name']):
                if proc.info['name'] in process_names:
                    try:
                        logger.LogEvt(f"Killing BurnIN process: PID={proc.info['pid']}, Name={proc.info['name']}")
                        proc.kill()
                        killed_count += 1
                    except Exception as e:
                        logger.LogErr(f"Failed to kill process {proc.info['pid']}: {e}")
            
            if killed_count > 0:
                logger.LogEvt(f'Killed {killed_count} BurnIN process(es)')
                time.sleep(2)  # Wait for processes to terminate
            else:
                logger.LogEvt('No running BurnIN processes found')
                
        except Exception as e:
            logger.LogErr(f'Error while killing BurnIN processes: {e}')
    
    def is_installed(self):
        """
        Check if BurnIN is installed
        
        Returns:
            bool: True if installed, False otherwise
        """
        exe = os.path.join(self.InstallPath, 'bit.exe')
        return os.path.exists(exe)

    def WaitTestDone_no_async(self):
        diaBoxOK = self.Windows.child_window(title="OK", auto_id="1", control_type="Button", found_index=0)
        diaIncorrectFileBtn = self.App.window(title='Incorrect file').child_window(control_type="Button", auto_id="2", found_index=0)
        statusImage = self.Windows.child_window(auto_id="14004", control_type="Image")
        while True:
            if diaBoxOK.exists(timeout=1):
                diaBoxOK.click()
            if diaIncorrectFileBtn.exists(timeout=1):
                diaIncorrectFileBtn.click()
            if statusImage.exists(timeout=1):
                testStatus = statusImage.texts()[0].upper().replace(" ", "")
                if "RUNNING" in testStatus or "STARTING" in testStatus:
                    r = re.search("\((\d+)ERRORS\)", testStatus)
                    if r:
                        #print(r.group(1))
                        if int(r.group(1)) > 0:
                            print("ERROR DURING RUNNING ,Test Fail")
                            # os.system("pause")
                            self.status = 'error'
                            self.debug = 'WaitTestDone_no_async RUNNING'
                            return False, "'" + testStatus + "'"
                elif "TESTSPASSED" in testStatus:
                    self.status = 'passed'
                    return True, ""
                else:
                    self.status = 'error'
                    return False, "'" + testStatus + "'"
            if self.break_signal:
                return True, ""
            time.sleep(2)
            
    def ScreenShot(self):
        self.Windows.set_focus()
        screen = pyautogui.screenshot()
        screen.save(os.path.join(self.LogPath.replace(".log",".png")))
        return
    
    

    def get_file_version_info(self):
        try:
            self.Installer_name = os.path.basename(self.Installer)
            version_info = win32api.GetFileVersionInfo(self.Installer, "\\")
            file_version_ms   = version_info.get('FileVersionMS', 0)
            file_version_ls   = version_info.get('FileVersionLS', 0)
            major             = (file_version_ms >> 16) & 0xFFFF
            minor             = file_version_ms & 0xFFFF
            build             = (file_version_ls >> 16) & 0xFFFF
            revision          = file_version_ls & 0xFFFF
            self.file_version = f"{major}.{minor}.{build}.{revision}"
            logger.LogEvt(f'{self.Installer_name} File Version : {self.file_version}')
            return self.Installer_name, self.file_version
        except Exception as e:
            logger.LogEvt(f'{str(e)}')
            return ""