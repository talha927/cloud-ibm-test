IBM_GEN2_PRE_REQ_FOR_WINDOWS_POWERSHELL_SCRIPT = r"""#ps1_sysnative
$DirPath = "c:\temp"
New-Item -ItemType "directory" -Path $DirPath | Out-Null;
[Net.ServicePointManager]::SecurityProtocol = "tls12, tls11, tls"
#Enabling Task History
wevtutil set-log Microsoft-Windows-TaskScheduler/Operational /enabled:true
#Downloading Precheck script and storing on c:\temp
$PrecheckFilePath = "https://github.com/IBM-Cloud/vpc-server-migration/blob/main/server-migration-scripts/windows_precheck.ps1?raw=true"
$PrecheckScript = "windows_precheck.ps1"
Invoke-WebRequest -Uri $PrecheckFilePath -OutFile $DirPath\$PrecheckScript -UseBasicParsing
#Creating a Task on startup for Installing the dependencies
$Action = New-ScheduledTaskAction -Execute 'Powershell.exe' -Argument $DirPath\$PrecheckScript
$Trigger = New-ScheduledTaskTrigger -AtStartup
$Principal = New-ScheduledTaskPrincipal -UserID "NT AUTHORITY\SYSTEM" -LogonType ServiceAccount -RunLevel Highest
Register-ScheduledTask -TaskName "Precheckscript" -TaskPath "\CustomTasks\" -Action $Action -Trigger $Trigger -Principal $Principal -Description "The task will run script to install software." -ErrorAction Stop
#Downloading the User Script which should be performed post pre-installation
$UserScriptFilePath = "https://github.com/IBM-Cloud/vpc-server-migration/blob/main/server-migration-scripts/user_defined.ps1?raw=true"
$UserScript = "user_defined.ps1"
Invoke-WebRequest -Uri $UserScriptFilePath -OutFile $DirPath\$UserScript -UseBasicParsing
#User has to provide the command or action
$USER_COMMAND = 'C:\Windows\System32\Sysprep\Sysprep.exe /oobe /generalize /shutdown "/unattend:C:\Program Files\Cloudbase Solutions\Cloudbase-Init\conf\Unattend.xml";'
(Get-Content $DirPath\$UserScript).replace('YOUR_COMMAND', $USER_COMMAND) | Set-Content $DirPath\$UserScript
#Creating User task after completion of Precheck task which will disable the pre-check task
$TaskFilePath = "https://github.com/IBM-Cloud/vpc-server-migration/blob/main/server-migration-scripts/userscript_task.xml?raw=true"
$TaskFile = "userscript_task.xml"
Invoke-WebRequest -Uri $TaskFilePath -OutFile $DirPath\$TaskFile -UseBasicParsing
$HOSTNAME = Hostname
(Get-Content $DirPath\$TaskFile).replace('COMPUTERNAME', $HOSTNAME) | Set-Content $DirPath\$TaskFile
Register-ScheduledTask -TaskName "User_Task" -TaskPath "\CustomTasks\" -Xml (Get-Content "$DirPath\$TaskFile" | Out-String) -Force
Set-ScheduledTask -TaskName "User_Task" -TaskPath "\CustomTasks\" -Principal $principal
#Restarting the server to trigger the Pre-check task.
shutdown /r /t 120
"""


class InstanceMigrationConsts:
    CLASSIC_VSI = "CLASSIC_VSI"
    CLASSIC_IMAGE = "CLASSIC_IMAGE"
    COS_BUCKET_VHD = "COS_BUCKET_VHD"
    COS_BUCKET_VMDK = "COS_BUCKET_VMDK"
    COS_BUCKET_QCOW2 = "COS_BUCKET_QCOW2"
    ONLY_VOLUME_MIGRATION = "ONLY_VOLUME_MIGRATION"

    # If any of these three options are there, then the image exported will have a vhd format
    COS_BUCKET_VHD_USE_CASES = [
        CLASSIC_VSI, CLASSIC_IMAGE, COS_BUCKET_VHD
    ]
    COS_BUCKET_USE_CASES = [
        COS_BUCKET_VHD, COS_BUCKET_VMDK, COS_BUCKET_QCOW2
    ]
    ALL_MIGRATION_USE_CASES = [
        CLASSIC_VSI, CLASSIC_IMAGE, COS_BUCKET_VHD, COS_BUCKET_VMDK, COS_BUCKET_QCOW2, ONLY_VOLUME_MIGRATION
    ]
    ALL_IMAGE_CONVERSION_USE_CASES = [COS_BUCKET_VMDK, COS_BUCKET_VHD]
    RESTORE_ADMIN_USER_DATA = (
        '#ps1_sysnative\n\n$RootFolder="C:\\Users\\migration\\Administrator"\n'
        '\ndo\n{\n    $i = Test-Path "C:\\Users\\Administrator"\n    sleep 2\n    get-date\n\n}'
        " until ($i -eq $True)\n\n$SubFolders = Get-ChildItem -Path $RootFolder"
        " -Directory\n\nForeach ($SubFolder in $SubFolders) {\n  "
        '  $src="C:\\Users\\migration\\Administrator\\$SubFolder"\n   '
        ' $dst="C:\\Users\\Administrator\\$SubFolder"\n    mkdir $dst\n   '
        " Get-ChildItem -Path $src -Recurse | Move-Item -Destination $dst\n   "
        " Remove-Item $src -Recurse -Force -Confirm:$false\n}\n\nGet-ChildItem -Path "
        '"C:\\Users\\migration\\Administrator\\" -Recurse | Move-Item -Destination '
        '"C:\\Users\\Administrator\\"\nRemove-LocalUser -Name "migration"'
    )
    IBM_GEN2_PRE_REQ_FOR_WINDOWS_POWERSHELL_SCRIPT = IBM_GEN2_PRE_REQ_FOR_WINDOWS_POWERSHELL_SCRIPT
