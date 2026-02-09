import wmi 

def get_partition_info(): 
    c = wmi.WMI() 
    s = wmi.WMI(namespace='root/Microsoft/Windows/Storage')
    tmplist = [] 
    for physical_disk in c.Win32_DiskDrive ():
        # if physical_disk.Partitions == 0:
        #     tmpdict = {} 
        #     tmpdict["DiskDrive_BytesPerSector"]                 = physical_disk.BytesPerSector
        #     tmpdict["DiskDrive_Capabilities"]                   = physical_disk.Capabilities
        #     tmpdict["DiskDrive_CapabilityDescriptions"]         = physical_disk.CapabilityDescriptions
        #     tmpdict["DiskDrive_Caption"]                        = physical_disk.Caption
        #     tmpdict["DiskDrive_ConfigManagerErrorCode"]         = physical_disk.ConfigManagerErrorCode
        #     tmpdict["DiskDrive_ConfigManagerUserConfig"]        = physical_disk.ConfigManagerUserConfig
        #     tmpdict["DiskDrive_CreationClassName"]              = physical_disk.CreationClassName
        #     tmpdict["DiskDrive_Description"]                    = physical_disk.Description
        #     tmpdict["DiskDrive_DeviceID"]                       = physical_disk.DeviceID
        #     tmpdict["DiskDrive_FirmwareRevision"]               = physical_disk.FirmwareRevision
        #     tmpdict["DiskDrive_Index"]                          = physical_disk.Index
        #     tmpdict["DiskDrive_InterfaceType"]                  = physical_disk.InterfaceType
        #     tmpdict["DiskDrive_Manufacturer"]                   = physical_disk.Manufacturer
        #     tmpdict["DiskDrive_MediaLoaded"]                    = physical_disk.MediaLoaded
        #     tmpdict["DiskDrive_MediaType"]                      = physical_disk.MediaType
        #     tmpdict["DiskDrive_Model"]                          = physical_disk.Model
        #     tmpdict["DiskDrive_Name"]                           = physical_disk.Name
        #     tmpdict["DiskDrive_Partitions"]                     = physical_disk.Partitions
        #     tmpdict["DiskDrive_PNPDeviceID"]                    = physical_disk.PNPDeviceID
        #     tmpdict["DiskDrive_SCSIBus"]                        = physical_disk.SCSIBus
        #     tmpdict["DiskDrive_SCSILogicalUnit"]                = physical_disk.SCSILogicalUnit
        #     tmpdict["DiskDrive_SCSIPort"]                       = physical_disk.SCSIPort
        #     tmpdict["DiskDrive_SCSITargetId"]                   = physical_disk.SCSITargetId
        #     tmpdict["DiskDrive_SectorsPerTrack"]                = physical_disk.SectorsPerTrack
        #     tmpdict["DiskDrive_SerialNumber"]                   = physical_disk.SerialNumber
        #     tmpdict["DiskDrive_Size"]                           = physical_disk.Size
        #     tmpdict["DiskDrive_Status"]                         = physical_disk.Status
        #     tmpdict["DiskDrive_SystemCreationClassName"]        = physical_disk.SystemCreationClassName
        #     tmpdict["DiskDrive_SystemName"]                     = physical_disk.SystemName
        #     tmpdict["DiskDrive_TotalCylinders"]                 = physical_disk.TotalCylinders
        #     tmpdict["DiskDrive_TotalHeads"]                     = physical_disk.TotalHeads
        #     tmpdict["DiskDrive_TotalSectors"]                   = physical_disk.TotalSectors
        #     tmpdict["DiskDrive_TotalTracks"]                    = physical_disk.TotalTracks
        #     tmpdict["DiskDrive_TracksPerCylinder"]              = physical_disk.TracksPerCylinder
        #     tmplist.append(tmpdict) 
        #     continue
        for partition in physical_disk.associators("Win32_DiskDriveToDiskPartition"): 
            for logical_disk in partition.associators("Win32_LogicalDiskToPartition"): 
                for msft_physicaldisk in s.MSFT_PhysicalDisk():
                    if msft_physicaldisk.DeviceID == str(physical_disk.Index):

                        tmpdict = {} 
                        diskKeys = list(physical_disk.properties.keys())
                        for k in diskKeys:
                            tmpdict.update({"DiskDrive_{}".format(k):physical_disk.__getattr__(k)})

                        diskKeys = list(partition.properties.keys())
                        for k in diskKeys:
                            tmpdict.update({"DiskPartition_{}".format(k):partition.__getattr__(k)})

                        diskKeys = list(logical_disk.properties.keys())
                        for k in diskKeys:
                            tmpdict.update({"LogicalDisk_{}".format(k):logical_disk.__getattr__(k)})

                        diskKeys = list(msft_physicaldisk.properties.keys())
                        for k in diskKeys:
                            tmpdict.update({"PhysicalDisk_{}".format(k):msft_physicaldisk.__getattr__(k)})



                        # tmpdict["DiskDrive_BytesPerSector"]                 = physical_disk.BytesPerSector
                        # tmpdict["DiskDrive_Capabilities"]                   = physical_disk.Capabilities
                        # tmpdict["DiskDrive_CapabilityDescriptions"]         = physical_disk.CapabilityDescriptions
                        # tmpdict["DiskDrive_Caption"]                        = physical_disk.Caption
                        # tmpdict["DiskDrive_ConfigManagerErrorCode"]         = physical_disk.ConfigManagerErrorCode
                        # tmpdict["DiskDrive_ConfigManagerUserConfig"]        = physical_disk.ConfigManagerUserConfig
                        # tmpdict["DiskDrive_CreationClassName"]              = physical_disk.CreationClassName
                        # tmpdict["DiskDrive_Description"]                    = physical_disk.Description
                        # tmpdict["DiskDrive_DeviceID"]                       = physical_disk.DeviceID
                        # tmpdict["DiskDrive_FirmwareRevision"]               = physical_disk.FirmwareRevision
                        # tmpdict["DiskDrive_Index"]                          = physical_disk.Index
                        # tmpdict["DiskDrive_InterfaceType"]                  = physical_disk.InterfaceType
                        # tmpdict["DiskDrive_Manufacturer"]                   = physical_disk.Manufacturer
                        # tmpdict["DiskDrive_MediaLoaded"]                    = physical_disk.MediaLoaded
                        # tmpdict["DiskDrive_MediaType"]                      = physical_disk.MediaType
                        # tmpdict["DiskDrive_Model"]                          = physical_disk.Model
                        # tmpdict["DiskDrive_Name"]                           = physical_disk.Name
                        # tmpdict["DiskDrive_Partitions"]                     = physical_disk.Partitions
                        # tmpdict["DiskDrive_PNPDeviceID"]                    = physical_disk.PNPDeviceID
                        # tmpdict["DiskDrive_SCSIBus"]                        = physical_disk.SCSIBus
                        # tmpdict["DiskDrive_SCSILogicalUnit"]                = physical_disk.SCSILogicalUnit
                        # tmpdict["DiskDrive_SCSIPort"]                       = physical_disk.SCSIPort
                        # tmpdict["DiskDrive_SCSITargetId"]                   = physical_disk.SCSITargetId
                        # tmpdict["DiskDrive_SectorsPerTrack"]                = physical_disk.SectorsPerTrack
                        # tmpdict["DiskDrive_SerialNumber"]                   = physical_disk.SerialNumber
                        # tmpdict["DiskDrive_Size"]                           = physical_disk.Size
                        # tmpdict["DiskDrive_Status"]                         = physical_disk.Status
                        # tmpdict["DiskDrive_SystemCreationClassName"]        = physical_disk.SystemCreationClassName
                        # tmpdict["DiskDrive_SystemName"]                     = physical_disk.SystemName
                        # tmpdict["DiskDrive_TotalCylinders"]                 = physical_disk.TotalCylinders
                        # tmpdict["DiskDrive_TotalHeads"]                     = physical_disk.TotalHeads
                        # tmpdict["DiskDrive_TotalSectors"]                   = physical_disk.TotalSectors
                        # tmpdict["DiskDrive_TotalTracks"]                    = physical_disk.TotalTracks
                        # tmpdict["DiskDrive_TracksPerCylinder"]              = physical_disk.TracksPerCylinder
                        
                        # tmpdict["DiskPartition_BlockSize"]                  = partition.BlockSize
                        # tmpdict["DiskPartition_Bootable"]                   = partition.Bootable
                        # tmpdict["DiskPartition_BootPartition"]              = partition.BootPartition
                        # tmpdict["DiskPartition_Caption"]                    = partition.Caption
                        # tmpdict["DiskPartition_CreationClassName"]          = partition.CreationClassName
                        # tmpdict["DiskPartition_Description"]                = partition.Description
                        # tmpdict["DiskPartition_DeviceID"]                   = partition.DeviceID
                        # tmpdict["DiskPartition_DiskIndex"]                  = partition.DiskIndex
                        # tmpdict["DiskPartition_Index"]                      = partition.Index
                        # tmpdict["DiskPartition_Name"]                       = partition.Name
                        # tmpdict["DiskPartition_NumberOfBlocks"]             = partition.NumberOfBlocks
                        # tmpdict["DiskPartition_PrimaryPartition"]           = partition.PrimaryPartition
                        # tmpdict["DiskPartition_Size"]                       = partition.Size
                        # tmpdict["DiskPartition_StartingOffset"]             = partition.StartingOffset
                        # tmpdict["DiskPartition_SystemCreationClassName"]    = partition.SystemCreationClassName
                        # tmpdict["DiskPartition_SystemName"]                 = partition.SystemName
                        # tmpdict["DiskPartition_Type"]                       = partition.Type

                        # tmpdict["LogicalDisk_Access"]                       = logical_disk.Access
                        # tmpdict["LogicalDisk_Caption"]                      = logical_disk.Caption
                        # tmpdict["LogicalDisk_Compressed"]                   = logical_disk.Compressed
                        # tmpdict["LogicalDisk_CreationClassName"]            = logical_disk.CreationClassName
                        # tmpdict["LogicalDisk_Description"]                  = logical_disk.Description
                        # tmpdict["LogicalDisk_DeviceID"]                     = logical_disk.DeviceID
                        # tmpdict["LogicalDisk_DriveType"]                    = logical_disk.DriveType
                        # tmpdict["LogicalDisk_FileSystem"]                   = logical_disk.FileSystem
                        # tmpdict["LogicalDisk_FreeSpace"]                    = logical_disk.FreeSpace
                        # tmpdict["LogicalDisk_MaximumComponentLength"]       = logical_disk.MaximumComponentLength
                        # tmpdict["LogicalDisk_MediaType"]                    = logical_disk.MediaType
                        # tmpdict["LogicalDisk_Name"]                         = logical_disk.Name
                        # tmpdict["LogicalDisk_QuotasDisabled"]               = logical_disk.QuotasDisabled
                        # tmpdict["LogicalDisk_QuotasIncomplete"]             = logical_disk.QuotasIncomplete
                        # tmpdict["LogicalDisk_QuotasRebuilding"]             = logical_disk.QuotasRebuilding
                        # tmpdict["LogicalDisk_Size"]                         = logical_disk.Size
                        # tmpdict["LogicalDisk_SupportsDiskQuotas"]           = logical_disk.SupportsDiskQuotas
                        # tmpdict["LogicalDisk_SupportsFileBasedCompression"] = logical_disk.SupportsFileBasedCompression
                        # tmpdict["LogicalDisk_SystemCreationClassName"]      = logical_disk.SystemCreationClassName
                        # tmpdict["LogicalDisk_SystemName"]                   = logical_disk.SystemName
                        # tmpdict["LogicalDisk_VolumeDirty"]                  = logical_disk.VolumeDirty
                        # tmpdict["LogicalDisk_VolumeName"]                   = logical_disk.VolumeName
                        # tmpdict["LogicalDisk_VolumeSerialNumber"]           = logical_disk.VolumeSerialNumber

                        # tmpdict["PhysicalDisk_AdapterSerialNumber"]         = msft_physicaldisk.AdapterSerialNumber
                        # tmpdict["PhysicalDisk_AllocatedSize"]               = msft_physicaldisk.AllocatedSize
                        # tmpdict["PhysicalDisk_BusType"]                     = msft_physicaldisk.BusType
                        # tmpdict["PhysicalDisk_CannotPoolReason"]            = msft_physicaldisk.CannotPoolReason
                        # tmpdict["PhysicalDisk_CanPool"]                     = msft_physicaldisk.CanPool
                        # tmpdict["PhysicalDisk_DeviceId"]                    = msft_physicaldisk.DeviceId
                        # tmpdict["PhysicalDisk_FirmwareVersion"]             = msft_physicaldisk.FirmwareVersion
                        # tmpdict["PhysicalDisk_FriendlyName"]                = msft_physicaldisk.FriendlyName
                        # tmpdict["PhysicalDisk_FruId"]                       = msft_physicaldisk.FruId
                        # tmpdict["PhysicalDisk_HealthStatus"]                = msft_physicaldisk.HealthStatus
                        # tmpdict["PhysicalDisk_IsIndicationEnabled"]         = msft_physicaldisk.IsIndicationEnabled
                        # tmpdict["PhysicalDisk_IsPartial"]                   = msft_physicaldisk.IsPartial
                        # tmpdict["PhysicalDisk_LogicalSectorSize"]           = msft_physicaldisk.LogicalSectorSize
                        # tmpdict["PhysicalDisk_MediaType"]                   = msft_physicaldisk.MediaType
                        # tmpdict["PhysicalDisk_Model"]                       = msft_physicaldisk.Model
                        # tmpdict["PhysicalDisk_ObjectId"]                    = msft_physicaldisk.ObjectId
                        # tmpdict["PhysicalDisk_OperationalStatus"]           = msft_physicaldisk.OperationalStatus
                        # tmpdict["PhysicalDisk_PhysicalLocation"]            = msft_physicaldisk.PhysicalLocation
                        # tmpdict["PhysicalDisk_PhysicalSectorSize"]          = msft_physicaldisk.PhysicalSectorSize
                        # tmpdict["PhysicalDisk_SerialNumber"]                = msft_physicaldisk.SerialNumber
                        # tmpdict["PhysicalDisk_Size"]                        = msft_physicaldisk.Size
                        # tmpdict["PhysicalDisk_SpindleSpeed"]                = msft_physicaldisk.SpindleSpeed
                        # tmpdict["PhysicalDisk_SupportedUsages"]             = msft_physicaldisk.SupportedUsages
                        # tmpdict["PhysicalDisk_UniqueId"]                    = msft_physicaldisk.UniqueId
                        # tmpdict["PhysicalDisk_UniqueIdFormat"]              = msft_physicaldisk.UniqueIdFormat
                        # tmpdict["PhysicalDisk_Usage"]                       = msft_physicaldisk.Usage
                        # tmpdict["PhysicalDisk_VirtualDiskFootprint"]        = msft_physicaldisk.VirtualDiskFootprint
                        tmplist.append(tmpdict) 

    return tmplist 

def get_disk_info(): 
    c = wmi.WMI() 
    s = wmi.WMI(namespace='root/Microsoft/Windows/Storage')
    tmplist = [] 
    for physical_disk in c.Win32_DiskDrive ():
        for msft_physicaldisk in s.MSFT_PhysicalDisk():
            if msft_physicaldisk.DeviceID == str(physical_disk.Index):
                tmpdict = {} 
                diskKeys = list(physical_disk.properties.keys())
                for k in diskKeys:
                    tmpdict.update({"DiskDrive_{}".format(k):physical_disk.__getattr__(k)})

                diskKeys = list(msft_physicaldisk.properties.keys())
                for k in diskKeys:
                    tmpdict.update({"PhysicalDisk_{}".format(k):msft_physicaldisk.__getattr__(k)})
                    
                # tmpdict["DiskDrive_BytesPerSector"]                 = physical_disk.BytesPerSector
                # tmpdict["DiskDrive_Capabilities"]                   = physical_disk.Capabilities
                # tmpdict["DiskDrive_CapabilityDescriptions"]         = physical_disk.CapabilityDescriptions
                # tmpdict["DiskDrive_Caption"]                        = physical_disk.Caption
                # tmpdict["DiskDrive_ConfigManagerErrorCode"]         = physical_disk.ConfigManagerErrorCode
                # tmpdict["DiskDrive_ConfigManagerUserConfig"]        = physical_disk.ConfigManagerUserConfig
                # tmpdict["DiskDrive_CreationClassName"]              = physical_disk.CreationClassName
                # tmpdict["DiskDrive_Description"]                    = physical_disk.Description
                # tmpdict["DiskDrive_DeviceID"]                       = physical_disk.DeviceID
                # tmpdict["DiskDrive_FirmwareRevision"]               = physical_disk.FirmwareRevision
                # tmpdict["DiskDrive_Index"]                          = physical_disk.Index
                # tmpdict["DiskDrive_InterfaceType"]                  = physical_disk.InterfaceType
                # tmpdict["DiskDrive_Manufacturer"]                   = physical_disk.Manufacturer
                # tmpdict["DiskDrive_MediaLoaded"]                    = physical_disk.MediaLoaded
                # tmpdict["DiskDrive_MediaType"]                      = physical_disk.MediaType
                # tmpdict["DiskDrive_Model"]                          = physical_disk.Model
                # tmpdict["DiskDrive_Name"]                           = physical_disk.Name
                # tmpdict["DiskDrive_Partitions"]                     = physical_disk.Partitions
                # tmpdict["DiskDrive_PNPDeviceID"]                    = physical_disk.PNPDeviceID
                # tmpdict["DiskDrive_SCSIBus"]                        = physical_disk.SCSIBus
                # tmpdict["DiskDrive_SCSILogicalUnit"]                = physical_disk.SCSILogicalUnit
                # tmpdict["DiskDrive_SCSIPort"]                       = physical_disk.SCSIPort
                # tmpdict["DiskDrive_SCSITargetId"]                   = physical_disk.SCSITargetId
                # tmpdict["DiskDrive_SectorsPerTrack"]                = physical_disk.SectorsPerTrack
                # tmpdict["DiskDrive_SerialNumber"]                   = physical_disk.SerialNumber
                # tmpdict["DiskDrive_Size"]                           = physical_disk.Size
                # tmpdict["DiskDrive_Status"]                         = physical_disk.Status
                # tmpdict["DiskDrive_SystemCreationClassName"]        = physical_disk.SystemCreationClassName
                # tmpdict["DiskDrive_SystemName"]                     = physical_disk.SystemName
                # tmpdict["DiskDrive_TotalCylinders"]                 = physical_disk.TotalCylinders
                # tmpdict["DiskDrive_TotalHeads"]                     = physical_disk.TotalHeads
                # tmpdict["DiskDrive_TotalSectors"]                   = physical_disk.TotalSectors
                # tmpdict["DiskDrive_TotalTracks"]                    = physical_disk.TotalTracks
                # tmpdict["DiskDrive_TracksPerCylinder"]              = physical_disk.TracksPerCylinder

                # tmpdict["PhysicalDisk_AdapterSerialNumber"]         = msft_physicaldisk.AdapterSerialNumber
                # tmpdict["PhysicalDisk_AllocatedSize"]               = msft_physicaldisk.AllocatedSize
                # tmpdict["PhysicalDisk_BusType"]                     = msft_physicaldisk.BusType
                # tmpdict["PhysicalDisk_CannotPoolReason"]            = msft_physicaldisk.CannotPoolReason
                # tmpdict["PhysicalDisk_CanPool"]                     = msft_physicaldisk.CanPool
                # tmpdict["PhysicalDisk_DeviceId"]                    = msft_physicaldisk.DeviceId
                # tmpdict["PhysicalDisk_FirmwareVersion"]             = msft_physicaldisk.FirmwareVersion
                # tmpdict["PhysicalDisk_FriendlyName"]                = msft_physicaldisk.FriendlyName
                # #tmpdict["PhysicalDisk_FruId"]                       = msft_physicaldisk.FruId
                # tmpdict["PhysicalDisk_HealthStatus"]                = msft_physicaldisk.HealthStatus
                # tmpdict["PhysicalDisk_IsIndicationEnabled"]         = msft_physicaldisk.IsIndicationEnabled
                # tmpdict["PhysicalDisk_IsPartial"]                   = msft_physicaldisk.IsPartial
                # tmpdict["PhysicalDisk_LogicalSectorSize"]           = msft_physicaldisk.LogicalSectorSize
                # tmpdict["PhysicalDisk_MediaType"]                   = msft_physicaldisk.MediaType
                # tmpdict["PhysicalDisk_Model"]                       = msft_physicaldisk.Model
                # tmpdict["PhysicalDisk_ObjectId"]                    = msft_physicaldisk.ObjectId
                # tmpdict["PhysicalDisk_OperationalStatus"]           = msft_physicaldisk.OperationalStatus
                # tmpdict["PhysicalDisk_PhysicalLocation"]            = msft_physicaldisk.PhysicalLocation
                # tmpdict["PhysicalDisk_PhysicalSectorSize"]          = msft_physicaldisk.PhysicalSectorSize
                # tmpdict["PhysicalDisk_SerialNumber"]                = msft_physicaldisk.SerialNumber
                # tmpdict["PhysicalDisk_Size"]                        = msft_physicaldisk.Size
                # tmpdict["PhysicalDisk_SpindleSpeed"]                = msft_physicaldisk.SpindleSpeed
                # tmpdict["PhysicalDisk_SupportedUsages"]             = msft_physicaldisk.SupportedUsages
                # tmpdict["PhysicalDisk_UniqueId"]                    = msft_physicaldisk.UniqueId
                # tmpdict["PhysicalDisk_UniqueIdFormat"]              = msft_physicaldisk.UniqueIdFormat
                # tmpdict["PhysicalDisk_Usage"]                       = msft_physicaldisk.Usage
                # tmpdict["PhysicalDisk_VirtualDiskFootprint"]        = msft_physicaldisk.VirtualDiskFootprint
                tmplist.append(tmpdict) 
    return tmplist 


# Partition = get_partition_info()
# print(Partition)

# disk = get_disk_info()
# print(disk)
