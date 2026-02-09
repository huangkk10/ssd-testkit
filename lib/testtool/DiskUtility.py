from logging import exception
import wmi 
import lib.testtool.Diskinfo as Diskinfo
import lib.logger as logger
import win32com.client


def get_physical_id(driveletter=""): 
    diskinfo = Diskinfo.get_partition_info()
    result = [ x for x in diskinfo if driveletter in x['LogicalDisk_Name'] ]
    if len(result):
        getphysicalid = result[0]['PhysicalDisk_DeviceId']
    else:
        raise exception("get_physical_id() Exceptio: Unknown Physical ID")
    return getphysicalid

def get_driveletter(physicalid=""): 
    diskinfo = Diskinfo.get_partition_info()
    result = [ x for x in diskinfo if physicalid in x['PhysicalDisk_DeviceId'] ]
    driveletter = []
    try:
        if len(result):
            for x in result:
                if physicalid == x['PhysicalDisk_DeviceId']:
                    tmpResult = x['LogicalDisk_DeviceID']
                    driveletter.append(tmpResult)
        else:
            driveletter = ''
            # raise exception("get_driveletter() Exceptio: Unknown Drive Letter")
    except Exception as e:
        driveletter = ''
    return driveletter

def get_LogicalDisk_FreeSpace(driveletter=""): 
    diskinfo = Diskinfo.get_partition_info()
    result = [ x for x in diskinfo if driveletter in x['LogicalDisk_Name'] ]
    if len(result):
        FreeSpace = result[0]['LogicalDisk_FreeSpace']
    else:
        raise exception("get_LogicalDisk_FreeSpace() Exceptio: Unknown LogicalDisk_FreeSpace")
    return FreeSpace

def get_LogicalDisk_Size(driveletter=""): 
    diskinfo = Diskinfo.get_partition_info()
    result = [ x for x in diskinfo if driveletter in x['LogicalDisk_Name'] ]
    if len(result):
        Size = result[0]['LogicalDisk_Size']
    else:
        raise exception("get_LogicalDisk_Size() Exceptio: Unknown LogicalDisk_Size")
    return Size


def get_PhysicalDisk_BusType(physicalid=""): 
    '''
    # physical_drive_id =  "1"
    # bustype, bustype_name = DiskUtility.get_PhysicalDisk_BusType(physical_drive_id)
    # if bustype_name != "RAID" and bustype_name != "SATA" and bustype_name != "NVMe":
    #     msg = f'Please confirm your SSD disk type : {bustype_name} , physical_drive_id : {physical_drive_id} '
    #     raise Exception(msg)
    # https://learn.microsoft.com/en-us/previous-versions/windows/desktop/stormgmt/msft-physicaldisk
    

    '''
    bus_type_mapping = {
        0: "Unknown",
        1: "SCSI",
        2: "ATAPI",
        3: "ATA",
        4: "IEEE 1394",
        5: "SSA",
        6: "Fibre Channel",
        7: "USB",
        8: "RAID",
        9: "iSCSI",
        10: "Serial Attached SCSI (SAS)",
        11: "SATA",
        12: "Secure Digital (SD)",
        13: "Multimedia Card (MMC)",
        15: "File-Backed Virtual",
        16: "Storage Spaces",
        17: "NVMe",
        18: "Microsoft Reserved"
    }
    
    disk_type_mapping = {
        0: "Unknown",
        3: "HDD",
        4: "SSD"
    }
    diskinfo = Diskinfo.get_disk_info()
    result = [ x for x in diskinfo if physicalid in x['PhysicalDisk_DeviceId'] ]
    driveletter = []
    if len(result):
        for x in result:
            if physicalid == x['PhysicalDisk_DeviceId']:
                tmpResult = x['PhysicalDisk_BusType']
                # driveletter.append(tmpResult)
                BusType = tmpResult
                # print(type(BusType))
                bus_type_name = bus_type_mapping.get(BusType, "Unknown")
    else:
        raise exception("get_PhysicalDisk_BusType() Exceptio: Unknown Drive Letter")
    return BusType, bus_type_name

def check_dut_info(config):
    # This request form Hiro.
    # config = LoadConfig()
    dut_model_name = config['DiskUtility']['dut_model_name']
    dut_disk_mode = config['DiskUtility']['dut_disk_mode']
    results = get_dut_disk_info()
    results, model_name, device_id, drive_letter,disk_mode = get_dut_info(results, dut_model_name, dut_disk_mode)
    logger.LogEvt(f'get_dut_info() : Model Name={model_name}, Device ID={device_id}, Drive Letter={drive_letter}, Disk Mode={disk_mode}')
    if device_id == '':
        msg = f"Unknow Device ID: Fail"
        raise Exception(msg)
    
    # total_count = check_dut_count(results, keys = ["NVMe", "SATA", "RAID"])
    # if total_count > 1:
    #     msg = f"Detected {total_count} Dut disk count: Fail"
    #     raise Exception(msg)

    # result = find_disk_info_key_type_by_keys(results, "Device ID", device_id, "Bus Type")
    # if result not in ["NVMe", "SATA", "RAID"]:
    #         msg = f'Please confirm your SSD disk type : {result} : Device ID : {device_id}'
    #         raise Exception(msg)
    return results, model_name, device_id, drive_letter,disk_mode


def get_dut_disk_info():
    c = wmi.WMI(namespace="root/Microsoft/Windows/Storage")
    w = win32com.client.GetObject('winmgmts:')
    disk_drives = w.InstancesOf('Win32_DiskDrive')
    
    bus_type_mapping = {
        0: "Unknown",
        1: "SCSI",
        2: "ATAPI",
        3: "ATA",
        4: "IEEE 1394",
        5: "SSA",
        6: "Fibre Channel",
        7: "USB",
        8: "RAID",
        9: "iSCSI",
        10: "Serial Attached SCSI (SAS)",
        11: "SATA",
        12: "Secure Digital (SD)",
        13: "Multimedia Card (MMC)",
        15: "File-Backed Virtual",
        16: "Storage Spaces",
        17: "NVMe",
        18: "Microsoft Reserved"
    }
    
    disk_type_mapping = {
        0: "Unknown",
        3: "HDD",
        4: "SSD"
    }
    primary_count = 0
    secondary_count = 0
    secondary_wo_usb_count = 0
    bus_type_count = {}
    disk_drive_info = {}
    disk_info = []
    
    for disk_drive in disk_drives:
        disk_drive_info[disk_drive.Index] = disk_drive.Model
    
    physical_disks = c.MSFT_PhysicalDisk()
    
    for disk in physical_disks:
        bus_type = bus_type_mapping.get(disk.BusType, "Unknown")
        disk_type = disk_type_mapping.get(disk.MediaType, "Unknown")
        
        if bus_type in bus_type_count:
            bus_type_count[bus_type] += 1
        else:
            bus_type_count[bus_type] = 1
        
        model_name = disk_drive_info.get(int(disk.DeviceID), "Unknown")
        DriveLetter = get_driveletter(physicalid=disk.DeviceID)
        DiskMode = "primary" if ("C:" in DriveLetter) else "secondary"

        if DiskMode == "primary":
            primary_count += 1
        else:
            secondary_count += 1
            if bus_type != 'USB':
                secondary_wo_usb_count += 1

        logger.LogEvt(f"Model Name   : {model_name}")
        logger.LogEvt(f"Bus Type     : {bus_type}")
        logger.LogEvt(f"Disk Type    : {disk_type}")
        logger.LogEvt(f"Device ID    : {disk.DeviceID}")
        logger.LogEvt(f"Drive Letter : {DriveLetter}")
        logger.LogEvt(f"Disk Mode    : {DiskMode}")
        logger.LogEvt("=" * 40)
        disk_info.append({
            "Model Name": model_name,
            "Bus Type": bus_type,
            "Disk Type": disk_type,
            "Device ID": disk.DeviceID,
            "Drive Letter": DriveLetter,
            "Disk Mode": DiskMode
        })
            
    bus_type_results = []
    for bus_type, count in bus_type_count.items():
        # status = "Fail" if count >= 2 and (bus_type in ["SATA", "NVMe", "RAID"]) else "Pass"
        bus_type_results.append({
            "Bus Type": bus_type,
            "Count": count
        })
        logger.LogEvt(f"Bus Type: {bus_type}, Count: {count}")
    logger.LogEvt(f'Primary Count  : {primary_count}')
    logger.LogEvt(f'Secondary Count: {secondary_count}')
    logger.LogEvt(f'Secondary W/O USB Count: {secondary_wo_usb_count}')
    logger.LogEvt("=" * 40)
    results = {
        "Disk Info": disk_info,
        "Bus Type Results": bus_type_results,
        "Primary Count": primary_count,
        "Secondary Count": secondary_count,
        "Secondary WO USB Count":secondary_wo_usb_count
    }
    # logger.LogEvt(results)
    return results

def find_disk_info_key_type_by_keys(results, search_key1, search_value1, search_key2):
    '''        
    result = DiskUtility.find_disk_info_key_type_by_keys(results, "Device ID", physical_drive_id, "Bus Type")
    if result not in ["NVMe", "SATA", "RAID"]:
            msg = f'Please confirm your SSD disk type : {result} : Device ID : {physical_drive_id}'
            raise Exception(msg)
    '''
    for entry in results['Disk Info']:
        if entry.get(search_key1) == search_value1:
            result = entry.get(search_key2)
            return result
    return None

def find_bus_type_results_key_type_by_keys(results, search_key1, search_value1, search_key2):
    # results = get_dut_disk_info()
    for entry in results['Bus Type Results']:
        if entry.get(search_key1) == search_value1:
            result = entry.get(search_key2)
            return result
    return 0

def get_dut_info(results, key, dut_disk_mode):

    disk_mode_mapping = {
        "0": "primary",
        "1": "secondary",
        "2": "secondary_wo_usb"
    }

    default_disk_mode = "unknown"
    dut_disk_mode = disk_mode_mapping.get(dut_disk_mode, default_disk_mode)
    if dut_disk_mode == default_disk_mode:
        raise Exception(f'Unknown Dut disk mode.')
    secondary_count = results['Secondary Count']
    secondary_wo_usb_count = results['Secondary WO USB Count']

    result, model_info_dict = check_duplicate_model_name(results, key, dut_disk_mode)
    if not result:
        # print(model_info_dict)
        raise Exception(f'Confirm Duplicate Mode Name.')
    
    for disk_info in results['Disk Info']:
        model_name = disk_info['Model Name']
        bus_type = disk_info['Bus Type']
        device_id = disk_info['Device ID']
        drive_letter = disk_info['Drive Letter']
        disk_mode = disk_info['Disk Mode']

        if dut_disk_mode == 'primary' :
            if "primary" in disk_mode.lower():
                update_count_in_bus_type_results(results, bus_type)
                return results, model_name, device_id, drive_letter, disk_mode

        elif dut_disk_mode == 'secondary' and disk_mode.lower() != 'primary' and secondary_count == 1 and "secondary" in disk_mode.lower():
            update_count_in_bus_type_results(results, bus_type)
            return results, model_name, device_id, drive_letter, disk_mode

        elif key != '' and key.lower() in model_name.lower() and dut_disk_mode == 'secondary' and disk_mode.lower() != 'primary' and "secondary" in disk_mode.lower():
            update_count_in_bus_type_results(results, bus_type)
            return results, model_name, device_id, drive_letter, disk_mode
        
        elif dut_disk_mode == 'secondary_wo_usb' and disk_mode.lower() != 'primary' and bus_type != "USB" and secondary_wo_usb_count == 1 and "secondary" in disk_mode.lower():
            update_count_in_bus_type_results(results, bus_type)
            return results, model_name, device_id, drive_letter, disk_mode
        
        elif key != '' and key.lower() in model_name.lower() and dut_disk_mode == 'secondary_wo_usb' and disk_mode.lower() != 'primary' and bus_type != "USB" and  "secondary" in disk_mode.lower():
            update_count_in_bus_type_results(results, bus_type)
            return results, model_name, device_id, drive_letter, disk_mode
        
        elif key != '' and dut_disk_mode == 'unknown' and (key.lower() in model_name.lower()):
            update_count_in_bus_type_results(results, bus_type)
            return results, model_name, device_id, drive_letter, disk_mode

        # if key != '' and (key.lower() in model_name.lower() and dut_disk_mode.lower() in disk_mode.lower()):
        elif key != '' and (key.lower() in model_name.lower() and dut_disk_mode.lower() in disk_mode.lower()):
            update_count_in_bus_type_results(results, bus_type)
            return results, model_name, device_id, drive_letter, disk_mode
    else:
        if dut_disk_mode == 'secondary_wo_usb' :
            raise Exception(f'Not match "{key}" model name and DUT disk mode {dut_disk_mode} and secondary without USB count {secondary_wo_usb_count}.')
        elif dut_disk_mode == 'secondary':
            raise Exception(f'Not match "{key}" model name and DUT disk mode {dut_disk_mode} and secondary with USB count {secondary_count}.')
        else:
            raise Exception(f'Unknown model name and DUT disk mode {dut_disk_mode}.')
        
def check_duplicate_model_name(results,key, dut_disk_mode):
    '''
    result, model_info_dict = check_duplicate_model_name(results, key, dut_disk_mode)
    if not result:
        # print(model_info_dict)
        raise Exception(f'Confirm Duplicate Mode Name.')
    '''
    model_info_dict = {}
    for disk_info in results['Disk Info']:
        model_name = disk_info['Model Name']
        bus_type = disk_info['Bus Type']
        device_id = disk_info['Device ID']
        drive_letter = disk_info['Drive Letter']
        disk_mode = disk_info['Disk Mode']
        if key != '' and key.lower() in model_name.lower():
            if dut_disk_mode == 'secondary' and disk_mode.lower() != 'primary' and "secondary" in disk_mode.lower():
                add_to_dict(model_info_dict, model_name, bus_type, device_id, drive_letter, disk_mode)
            elif dut_disk_mode == 'secondary_wo_usb' and disk_mode.lower() != 'primary' and bus_type != "USB" and "secondary" in disk_mode.lower():
                add_to_dict(model_info_dict, model_name, bus_type, device_id, drive_letter, disk_mode)

    failed_model_names = []

    for model_name, info_list in model_info_dict.items():
        if len(info_list) >= 2:
            failed_model_names.append(model_name)

    if failed_model_names:
        logger.LogEvt("=" * 40)
        logger.LogEvt("Confirm Duplicate Mode Name")
        logger.LogEvt("=" * 40)
        for model_name in failed_model_names:
            for info in model_info_dict[model_name]:
                logger.LogEvt(f"Model Name  : {model_name}")
                logger.LogEvt(f"Bus Type    : {info['Bus Type']}")
                logger.LogEvt(f"Device ID   : {info['Device ID']}")
                logger.LogEvt(f"Drive Letter: {info['Drive Letter']}")
                logger.LogEvt(f"Disk Mode   : {info['Disk Mode']}")
                logger.LogEvt("=" * 40)
        return False, model_info_dict
    return True, model_info_dict

def add_to_dict(model_info_dict, model_name, bus_type, device_id, drive_letter, disk_mode):
    if model_name in model_info_dict:
        model_info_dict[model_name].append({
            'Bus Type': bus_type,
            'Device ID': device_id,
            'Drive Letter': drive_letter,
            'Disk Mode': disk_mode
        })
    else:
        model_info_dict[model_name] = [{
            'Bus Type': bus_type,
            'Device ID': device_id,
            'Drive Letter': drive_letter,
            'Disk Mode': disk_mode
        }]
    return

def update_count_in_bus_type_results(results, target_bus_type):
    for result in results['Bus Type Results']:
        bus_type = result['Bus Type']
        if bus_type == target_bus_type:
            result['Count'] -= 1
            return
def check_dut_bus_type(results,device_id, type):
    result = find_disk_info_key_type_by_keys(results, "Device ID", device_id, "Bus Type")
    if result not in type:
            msg = f'Please confirm your SSD disk type : {result} : Device ID : {device_id}'
            raise Exception(msg)

def check_dut_count(results, keys):
    '''        
    total_count = DiskUtility.check_dut_count(results, keys = ["NVMe", "SATA", "RAID"])
    if total_count > 1:
        msg = f"Detected {total_count} disk count: Fail"
        raise Exception(msg)
    '''
    total_count = 0
    for key in keys:
        count = find_bus_type_results_key_type_by_keys(results, "Bus Type", key, "Count")
        total_count += count
    # logger.LogEvt(f'Total Count: {total_count}')
    return total_count


def get_driveletter_info(driveletter="", Key = "" ): 
    # logger.LogEvt(get_driveletter_info(driveletter="C:",Key = "BusType"))
    diskinfo = Diskinfo.get_partition_info()
    result = [ x for x in diskinfo if driveletter in x['LogicalDisk_Name'] ]
    if len(result):
        info = result[0][Key]
    else:
        raise Exception("get_driveletter_info() Exceptio: Unknown {}".format(Key))
    return info

def get_PNPDeviceID(physicalid=""):
    # get_PNPDeviceID(0)
    c = wmi.WMI()
    disk_drives = c.Win32_DiskDrive()
    PNPDeviceID = ''
    for drive in disk_drives:
        if f"PHYSICALDRIVE{physicalid}" in drive.DeviceID:
            PNPDeviceID = drive.PNPDeviceID
            # logger.LogEvt(drive.PNPDeviceID)
            break
    if PNPDeviceID == '':
        raise Exception("get_PNPDeviceID() Exceptio: Unknown PNPDeviceID")
    return PNPDeviceID

# print(get_driveletter_info(driveletter="C:",Key = "PhysicalDisk_BusType"))
# print(get_LogicalDisk_FreeSpace(driveletter="E:"))
# print(get_physical_id(driveletter="C:"))
# print(get_driveletter(physicalid="1"))
# print(get_PhysicalDisk_BusType(physicalid="5"))

