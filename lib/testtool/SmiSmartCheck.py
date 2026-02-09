import lib.logger as logger
from shutil import copy2
import subprocess
import os
import configparser
import signal
import asyncio
import pathlib
import json
from pathlib import Path
import shutil
import pywinauto
from pywinauto import Application
from pywinauto import keyboard
import time
import math
import datetime
from async_timeout import timeout
import time

class SmiSmartCheckError(Exception):
    pass

class SmiSmartCheck:

    def __init__(self):
        self.App = None
        self.ScanTask = None
        self.BatPath = './bin/SmiWinTools/SmartCheck.bat'
        self.CofingIniPath = './bin/SmiWinTools/config/SMART.ini'
        self.LogPath = './testlog'
        self.LogPrefix = ''
        self.TempRunCardPath = os.environ["TEMP"].replace("\\", "/")+"/RunCard.ini"
        # global section
        self.case = '1'
        self.Total_cycle = '0'
        self.total_time = '10080'
        self.dut_id = ''
        self.Timeout = 0
        self.enable_monitor_link = 'False'
        self.enable_check_link = 'False'
        self.enable_monitor_smart = 'True'
        self.Status = True
        self.break_signal = False
        self.Auto_Close = True
        self.retryMax = 30
        self.FIRSTRUN = 1
        self.SYNCTIME = 1
        return

    def SetConfigByPath(self,Path:str):
        with open(Path, newline='') as f:
            self.SetConfig(json.load(f))
        return

    def SetConfig(self,dictConfig:dict):
        for key,value in dictConfig.items():
            setattr(self,key,value)
        return
    
    def DeleteLogDir(self):
        try:
            absLogPath = os.path.abspath( self.LogPath)
            dirPath = pathlib.Path(absLogPath).parent.resolve()
            baseName = self.LogPrefix+os.path.basename(absLogPath)
            output_dir = os.path.join( dirPath,baseName )
            if os.path.exists(os.path.abspath(output_dir)):
                shutil.rmtree( os.path.abspath(output_dir))
        except:
            return


    def __SetSmiwintoolConfigIni__(self,session,key,value):
        '''
        smiSmartCheck.__SetSmiwintoolConfigIni__('nvme-1.4c_lid_2_ugsd','attr_limit_25','diff<2')
        '''
        try:
            CofingIniPath = os.path.abspath(self.CofingIniPath)
            ini = configparser.ConfigParser()
            ini.read(CofingIniPath)
            ini[session][key]= value
            with open(CofingIniPath, 'w') as configfile:
                ini.write(configfile)
        except Exception as e:
            logger.LogErr('__SetSmiwintoolConfigIni__() error:'+str(e))

    def __SetSmartIni__(self,session,key,value):
        try:
            iniPath = os.path.abspath(self.BatPath.replace(".bat",".ini"))
            ini = configparser.ConfigParser()
            ini.read(iniPath)
            ini[session][key]= value
            with open(iniPath, 'w') as configfile:
                ini.write(configfile)
        except Exception as e:
            logger.LogErr('__SetSmartIni_() error:'+str(e))
    
    def __SetSmartDefaultIniValue__(self):
        absLogPath = os.path.abspath( self.LogPath)
        dirPath = pathlib.Path(absLogPath).parent.resolve()
        baseName = self.LogPrefix+os.path.basename(absLogPath)
        output_dir = os.path.join( dirPath,baseName )
        self.__SetSmartIni__('global', 'case', f'{self.case}')
        self.__SetSmartIni__('global','output_dir',output_dir)
        self.__SetSmartIni__('global','total_cycle',self.Total_cycle)
        self.__SetSmartIni__('global','total_time',self.total_time)
        self.__SetSmartIni__('global','dut_id',f'{self.dut_id}')
        self.__SetSmartIni__('global','enable_monitor_link',f'{self.enable_monitor_link}')
        self.__SetSmartIni__('global','enable_check_link',f'{self.enable_check_link}')
        self.__SetSmartIni__('global','enable_monitor_smart',f'{self.enable_monitor_smart}')

    def __SetSmartDefaultBatValue__(self):
        bat_file_path = os.path.abspath(self.BatPath)
        with open(bat_file_path, 'r', encoding='utf-8') as file:
            bat_content = file.readlines()

        new_content = []
        for line in bat_content:
            stripped_line = line.strip()
            if stripped_line.startswith("set FIRSTRUN="):
                new_content.append(f"set FIRSTRUN={self.FIRSTRUN}\n")
            elif stripped_line.startswith("set SYNCTIME="):
                new_content.append(f"set SYNCTIME={self.SYNCTIME}\n")
            else:
                new_content.append(line)

        with open(bat_file_path, 'w', encoding='utf-8') as file:
            file.writelines(new_content)



    async def RunUntilClose(self,Cycle,Time):
        if Cycle:
            self.__SetSmartIni__('global','total_cycle',str(Cycle))
        if Time:
            self.__SetSmartIni__('global','total_cycle',str(Time))

    
    async def RunProcedure(self):
        self.__SetSmartDefaultIniValue__()
        self.DeleteLogDir()
        self.__Open__()
        result = False
        msg = ""
        try:
            if self.Timeout > 0:
                #result = await asyncio.wait_for(self.ScanTask,timeout=Timeout)
                async with timeout(self.Timeout):
                    result,msg = await self.__ScanRunCard__()
            else:
                result,msg = await self.__ScanRunCard__()
            
            return result,msg
            
        except asyncio.TimeoutError:
            if self.Auto_Close:
                self.Close()
            return True,"Smart Check RunProcedure Timeout."
        except Exception as e:
            logger.LogErr(e)
            return False,str(e)
    
    async def RunProcedureWithNoAwait(self,CallBack):
        self.__SetSmartDefaultIniValue__()
        self.CallBack = CallBack
        self.DeleteLogDir()
        self.__Open__()
        try:
            if self.Timeout > 0:
                #result = await asyncio.wait_for(self.ScanTask,timeout=Timeout)
                async with timeout(self.Timeout):
                    result,msg = await self.__ScanRunCard__()
            else:
                result,msg = await self.__ScanRunCard__()

            if not result:
                self.Status = False
                raise SmiSmartCheckError("SmiSmartCheckError Test Error:{}".format(str(e)))

        except asyncio.TimeoutError:
            if self.Auto_Close:
                self.Close()
            return True 
        except Exception as e:
            logger.LogErr(e)
            if self.Auto_Close:
                self.Close()
            raise SmiSmartCheckError("SmiSmartCheckError Test Error:{}".format(str(e)))

    # implement without async for threading purpose.
    def _ScanRunCard_no_more_async_plz(self):
        try:
            msg = ""
            retryCount = 0
            initial_wait_logged = False
            while True:
                # if self.Check_pid(self.App.pid):
                if self.App.returncode != 0:
                    test_result, err_msg = self.ReadRunCard()
                    if (err_msg):
                        if err_msg.lower().strip() == "no error":
                            if test_result.lower() == "pass":
                                logger.LogEvt('Smart Check Test Pass!')
                                return True, test_result
                            retryCount = 0
                        else:
                            return False, err_msg
                    else:
                        # RunCard.ini not ready yet, waiting for SmartCheck to initialize
                        if not initial_wait_logged:
                            logger.LogEvt(f"Waiting for SmartCheck to initialize and create RunCard.ini (max retries: {self.retryMax})...")
                            initial_wait_logged = True
                        
                        if(retryCount>self.retryMax):
                            msg = "Retry ReadRunCard() retryCount>"+str(self.retryMax)+". Open SmiSmartCheck Failed."
                            logger.LogErr(msg)
                            return False,msg
                        
                        if retryCount > 0 and retryCount % 10 == 0:
                            logger.LogEvt(f"Still waiting for SmartCheck initialization... (retry {retryCount}/{self.retryMax})")
                        
                        time.sleep(1)
                        retryCount += 1
                else:

                    test_result, err_msg = self.ReadRunCard()
                    logger.LogEvt('Smart Check Close! Read RunCard Status')
                    logger.LogEvt('test_result=' + str(test_result))
                    logger.LogEvt('err_msg=' + str(err_msg))
                    if (err_msg):
                        if err_msg.lower().strip() == "no error":
                            if test_result == "passed":
                                return True, msg
                            elif test_result == "ongoing":
                                msg = "Warnning:SMART Check was Closed, But RunCard Status still ongoing."
                                logger.LogEvt(msg)
                                return True, msg
                        else:
                            return False, err_msg
                    else:
                        return False, "Abnormal End. Error:" + str(err_msg)
                if self.break_signal is True:
                    break
                time.sleep(3)
            return True, ""
        except Exception as e:
            logger.LogErr(str(e))
            return False, "Exception:" + str(e)

    def SmiSmartCheck_start(self):
        self.__SetSmartDefaultIniValue__()
        self.DeleteLogDir()
        self.__Open__()
        try:
            result,msg = self._ScanRunCard_no_more_async_plz()

            if not result:
                self.Status = False
                raise Exception("SmiSmartCheckError Test Error:{}".format(str(msg)))
        except Exception as e:
            logger.LogErr(e)
            if self.Auto_Close:
                self.Close()
            raise SmiSmartCheckError("SmiSmartCheckError Test Error:{}".format(str(e)))

    def RunProcedure_sync(self):
        """
        Synchronous version of RunProcedure for multithreading.

        This method provides the same functionality as RunProcedure() but uses time.sleep
        instead of await asyncio.sleep, making it suitable for use in multithreaded contexts.

        Returns:
            tuple: (result, msg)
                - result (bool): True if all checks pass, False if there is an error
                - msg (str): result message or error information
        """
        logger.LogEvt("[SmartCheck-Sync] Starting synchronous SmartCheck monitoring")
        self.__SetSmartDefaultIniValue__()
        self.DeleteLogDir()
        self.__Open__()
        
        result = False
        msg = ""
        try:
            # If a timeout is set
            if self.Timeout > 0:
                logger.LogEvt(f"[SmartCheck-Sync] Set timeout: {self.Timeout} seconds")
                start_time = time.time()
                result, msg = self.__ScanRunCard_sync__()
                elapsed_time = time.time() - start_time
                
                if elapsed_time >= self.Timeout:
                    logger.LogEvt(f"[SmartCheck-Sync] Reached timeout: {elapsed_time:.1f} seconds")
                    if self.Auto_Close:
                        self.Close()
                    return True, "Smart Check RunProcedure Timeout."
            else:
                # No timeout limit
                logger.LogEvt("[SmartCheck-Sync] Running without timeout limit")
                result, msg = self.__ScanRunCard_sync__()
            
            logger.LogEvt(f"[SmartCheck-Sync] Monitoring completed: result={result}, msg={msg}")
            return result, msg
            
        except Exception as e:
            logger.LogErr(f"[SmartCheck-Sync] Exception: {e}")
            if self.Auto_Close:
                self.Close()
            return False, str(e)

    def __ScanRunCard_sync__(self):
        """
        Synchronous version of __ScanRunCard__ for multithreading.

        This method replicates the behavior of the async version but uses time.sleep
        instead of await asyncio.sleep to continuously monitor the SmartCheck process
        status and the RunCard.ini file.

        Returns:
            tuple: (result, msg)
                - result (bool): True if the test passed, False if there is an error
                - msg (str): test result message or error information
        """
        try:
            msg = ""
            retryCount = 0
            initial_wait_logged = False
            
            logger.LogEvt("[SmartCheck-Sync] Starting to scan RunCard")
            
            while True:
                # Check SmartCheck process status
                if self.App.returncode != 0:
                    # Process is still running
                    test_result, err_msg = self.ReadRunCard()
                    
                    if err_msg:
                        if err_msg.lower().strip() == "no error":
                            if test_result.lower() == "pass":
                                logger.LogEvt('[SmartCheck-Sync] Smart Check Test Pass!')
                                return True, test_result
                            retryCount = 0
                        else:
                            logger.LogErr(f"[SmartCheck-Sync] Detected error: {err_msg}")
                            return False, err_msg
                    else:
                        # RunCard.ini not ready yet, wait for SmartCheck to initialize
                        if not initial_wait_logged:
                            logger.LogEvt(f"[SmartCheck-Sync] Waiting for SmartCheck to initialize and create RunCard.ini (max retries: {self.retryMax})...")
                            initial_wait_logged = True
                        
                        if retryCount > self.retryMax:
                            msg = f"Retry ReadRunCard() retryCount > {self.retryMax}. Failed to open SmiSmartCheck."
                            logger.LogErr(f"[SmartCheck-Sync] {msg}")
                            return False, msg
                        
                        # Log progress every 10 retries
                        if retryCount > 0 and retryCount % 10 == 0:
                            logger.LogEvt(f"[SmartCheck-Sync] Still waiting for SmartCheck initialization... (retry {retryCount}/{self.retryMax})")
                        
                        time.sleep(1)
                        retryCount += 1
                else:
                    # Process has ended
                    test_result, err_msg = self.ReadRunCard()
                    logger.LogEvt('[SmartCheck-Sync] Smart Check closed! Read RunCard status')
                    logger.LogEvt(f'[SmartCheck-Sync] test_result={test_result}')
                    logger.LogEvt(f'[SmartCheck-Sync] err_msg={err_msg}')
                    
                    if err_msg:
                        if err_msg.lower().strip() == "no error":
                            if test_result == "passed":
                                return True, msg
                            elif test_result == "ongoing":
                                msg = "Warning: SMART Check closed but RunCard status is still ongoing."
                                logger.LogEvt(f"[SmartCheck-Sync] {msg}")
                                return True, msg
                        else:
                            return False, err_msg
                    else:
                        return False, f"Abnormal end. Error: {err_msg}"
                
                # Check interrupt signal
                if self.break_signal is True:
                    logger.LogEvt("[SmartCheck-Sync] Received interrupt signal, stopping monitoring")
                    break
                
                time.sleep(3)  # Check every 3 seconds
            
            return True, ""
            
        except Exception as e:
            logger.LogErr(f"[SmartCheck-Sync] Exception: {str(e)}")
            return False, f"Exception: {str(e)}"


    def __Open__(self):
        absPath = os.path.abspath(self.BatPath)
        self.App = subprocess.Popen(absPath, creationflags=subprocess.CREATE_NEW_CONSOLE)

        return
    
    

    async def __ScanRunCard__(self):
        try:
            msg = ""
            # retryMax = 5
            retryCount = 0
            while True:

                #if self.Check_pid(self.App.pid):
                print(self.App.returncode)
                if self.App.returncode != 0:
                    test_result,err_msg = self.ReadRunCard()
                    if(err_msg):
                        if err_msg.lower().strip() =="no error":
                            if test_result.lower() == "pass":
                                logger.LogEvt('Smart Check Test Pass!')
                                return True,test_result
                            retryCount = 0
                        else:
                            return False,err_msg
                    else:
                        if(retryCount>self.retryMax):
                            msg = "Retry ReadRunCard() retryCount>"+str(self.retryMax)+". Open SmiSmartCheck Failed."
                            logger.LogEvt(msg)
                            return False,msg
                        await asyncio.sleep(1)
                        retryCount += 1
                else:
                    
                    test_result,err_msg = self.ReadRunCard()
                    logger.LogEvt('Smart Check Close! Read RunCard Status')
                    logger.LogEvt('test_result='+str(test_result))
                    logger.LogEvt('err_msg='+str(err_msg))
                    if(err_msg):
                        if err_msg.lower().strip() =="no error":
                            if test_result == "passed":
                                return True,msg
                            elif test_result == "ongoing":
                                msg = "Warnning:SMART Check was Closed, But RunCard Status still ongoing."
                                logger.LogEvt(msg)
                                return True,msg
                        else:
                            return False,err_msg
                    else:
                        return False,"Abnormal End. Error:"+str(err_msg)
                await asyncio.sleep(3)
        except Exception as e:
            logger.LogErr(str(e))
            return False,"Exception:"+str(e)

    def ReadRunCard(self):
        try:
            absLogPath = os.path.abspath( self.LogPath)
            dirPath = pathlib.Path(absLogPath).parent.resolve()
            baseName = self.LogPrefix+os.path.basename(absLogPath)
            output_dir = os.path.join( dirPath,baseName )
            runCardPath = os.path.join(output_dir,"RunCard.ini")
            if not os.path.exists(runCardPath):
                # Don't log every attempt - this is expected during initialization
                return False,""
            if not os.path.isfile(runCardPath):
                logger.LogErr('ReadRunCardFailed:'+runCardPath+' is not a file. ')
                return False,""
            copy2(runCardPath,self.TempRunCardPath)
            config = configparser.ConfigParser()
            config.read(self.TempRunCardPath)
            test_result = config['Test Status']['test_result']
            err_msg  = config['Test Status']['err_msg']
            return test_result,err_msg
        except Exception as e:
            print(e)
            return False,""
        
    def __Connect__(self):
        w_handle = pywinauto.findwindows.find_windows(title=u'Administrator:  SmartCheck')[0]
        self.Prossce = pywinauto.Application(backend="uia").connect(handle=w_handle)
        self.Window = self.Prossce.window(handle=w_handle)
        return
    
    def __Stop__(self):
        self.__Connect__()
        self.Window.set_focus()
        # keyboard.send_keys('^{VK_PAUSE}')
        keyboard.send_keys("^c")
        time.sleep(2)
        return

    def __Pause__(self):
        self.Window.set_focus()
        keyboard.send_keys('^{VK_PAUSE}')
        return
    
    def Close(self):
        if(self.ScanTask):
            self.ScanTask.cancel()
        if(self.App):
            os.kill(self.App.pid, signal.CTRL_BREAK_EVENT)
            os.kill(self.App.pid, signal.CTRL_C_EVENT)
            subprocess.call(['taskkill', '/F', '/T', '/PID',  str(self.App.pid)])
            #self.App.terminate()
            
        return
    
    def Check_pid(self,pid):        
        """ Check For the existence of a unix pid. """
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        else:
            return True


def TryFormat(FilePath):

    return
