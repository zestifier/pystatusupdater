# lilzestttt, 03/04/2025 and 04/04/2025
import platform
import socket
import ctypes
import sys
from datetime import datetime
import os
import psutil
import yaml
import time
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import shutil

scriptdir = os.path.dirname(__file__) 
with open(os.path.join(scriptdir, "config.yml"), "r") as conf:
    config = yaml.safe_load(conf)

if config["general"]["gpu"] == True:
    print("Using GPUtil libraries")
    import GPUtil

if platform.system() == "Windows" and config["general"]["wmisupport"] == True:
    print("Using WMI libraries")
    import wmi
    wmisupport = True
elif platform.system() == "Windows" and config["general"]["wmisupport"] == False:
    print("Running without WMI libraries, even though supported")
    wmisupport = False
elif platform.system() != "Windows" and config["general"]["wmisupport"] == True:
    print("You're attempting to import WMI libraries on a non-Windows system! This will probably fail!")
    import wmi
    wmisupport = True
elif platform.system() != "Windows" and config["general"]["wmisupport"] == False:
    print("Not loading WMI libraries due to incompatibility")
    wmisupport = False

def Distribute(message):
    if config['general']['sharemethod'] == "email":
        email = MIMEMultipart()
        email['From'] = config['email']['address']
        email['To'] = config['email']['recipient']
        email['Subject'] = "Status update for "+platform.node()+" - "+str(datetime.now())
        if config['general']['processlog'] == True:
            print("Attaching process log as requested")
            with open("processlog.txt", "r") as proclog:
                attachment = MIMEBase('application', 'octet-stream')
                attachment.set_payload(proclog.read())
                encoders.encode_base64(attachment)
                attachment.add_header('Content-Disposition', f'attachment; filename={"processlog.log"}')
                email.attach(attachment)
        email.attach(MIMEText(message, 'plain'))
        if config['email']['ssl'] == True:
           print("Using SSL to send email")
           try:
                with smtplib.SMTP_SSL(config['email']['server'], config['email']['port']) as server:
                    if config['email']['password'] == "":
                        print("No password specified, not attempting authentication")
                    else:
                        server.login(config['email']['address'], config['email']['password'])
                server.sendmail(config['email']['address'], config['email']['recipient'], email.as_string())
           except Exception as e:
                print(f"Failed. Error code {e}")
        elif config['email']['ssl'] == False:
            try:
                with smtplib.SMTP(config['email']['server'], config['email']['port']) as server:
                    if config['email']['password'] == "":
                        print("No password specified, not attempting authentication")
                    else:
                        server.login(config['email']['address'], config['email']['password'])
                    server.sendmail(config['email']['address'], config['email']['recipient'], email.as_string())
            except Exception as e:
                print(f"Failed. Error code {e}")
    elif config["general"]["sharemethod"] == "discord":
        if config["discord"]["bypasslengthlimit"] == False:
                    embed = {
                    "title": "Status update for "+str(platform.node()),
                    "color": int(config["discord"]["messagecolour"], 16),
                    "fields": [
                        {"name": str(datetime.now()), "value": message, "inline": True},
                    ],
                    }
                    data = {
                        "embeds": [embed],
                    }
                    requests.post(config["discord"]["webhook"], json=data)
        elif config["discord"]["bypasslengthlimit"] == True:
            with open(os.path.join(scriptdir, config["discord"]["filename"]), "w") as file:
                file.write(message)
            with open(os.path.join(scriptdir, config["discord"]["filename"]), "r") as file:
                response = requests.post(config["discord"]["webhook"], files={"file": file})
            if not response.status_code == 200:
                print("Error sending. Response code: "+str(response.status_code))
        if config["general"]["processlog"] == True:
            with open(os.path.join(scriptdir, "processlog.txt"), "r") as file:
                response = requests.post(config["discord"]["webhook"], files={"file": file})
            if not response.status_code == 200:
                print("Error sending process log. Response code: "+str(response.status_code))

def GetNetworkRate(recv, withUnits):
    iocountersbefore = psutil.net_io_counters()
    time.sleep(1)
    iocountersafter = psutil.net_io_counters()
    bytes_sent_rate = iocountersafter.bytes_sent - iocountersbefore.bytes_sent
    bytes_recv_rate = iocountersafter.bytes_recv - iocountersbefore.bytes_recv
    if recv == True:
        return ConvertStorageToReasonableUnit(bytes_recv_rate, withUnits)
    elif recv == False:
        return ConvertStorageToReasonableUnit(bytes_sent_rate, withUnits)

def GetDriveUsageStats():
    drivestats = []
    for partition in psutil.disk_partitions():
        try:
            usage = psutil.disk_usage(partition.mountpoint)
            drivestats.append("Drive "+str(partition.device)+" mounted at "+str(partition.mountpoint)+" - "+str(usage.percent)+"% usage, "+ConvertStorageToReasonableUnit(usage.used,True)+" used, "+ConvertStorageToReasonableUnit(usage.free,True)+" free, "+ConvertStorageToReasonableUnit(usage.total,True)+" total")
        except PermissionError:
            print(f"Skipping "+str(partition.device)+" due to lack of permissions")
    return drivestats

def GetGPUInformation():
    gpuinfotable = []
    gpus = GPUtil.getGPUs()
    for gpu in gpus:
        try:
            gpufanSpeed = str(gpu.fanSpeed+"RPM") # rpm
        except AttributeError:
            print("Couldn't get fan speed of "+gpu.name)
            gpufanSpeed = "N/A"
        try:
            gpupowerUsage = str(gpu.powerUsage+"W") # watts
        except AttributeError:
            print("Couldn't get power usage of "+gpu.name)
            gpupowerUsage = "N/A"
        try:
            gpupciBusID = str(gpu.pciBusID)
        except AttributeError:
            print("Couldn't get PCI ID of "+gpu.name)
            gpupciBusID = "N/A"
        gpuinfotable.append(str(gpu.name)+", ID "+str(gpu.id)+" running driver version "+str(gpu.driver)+":\n"+"  VRAM usage: "+str(round(((gpu.memoryUsed / gpu.memoryTotal) * 100),1))+"% ("+ConvertStorageToReasonableUnit(gpu.memoryUsed*1000000,True)+" in use, "+ConvertStorageToReasonableUnit(gpu.memoryFree*1000000,True)+" free, "+ConvertStorageToReasonableUnit(gpu.memoryTotal*1000000,True)+" total)"+"\n"+"  Temperature: "+str(gpu.temperature)+"°C\n"+"  Fan speed: "+gpufanSpeed+"\n"+"  Power usage: "+gpupowerUsage+"\n"+"  PCI bus ID: "+gpupciBusID)
    return gpuinfotable

def RelaunchAsAdmin():
    if ctypes.windll.shell32.IsUserAnAdmin():
        return True
    else:
        print("Restarting program as admin (required to grab temps)...")
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
        sys.exit()

def GetTemperatures():
    temptable = []
    if platform.system() == "Linux":
        print("Using psutil to grab temps...")
        temps = psutil.sensors_temperatures()
        for sensor, readings in temps.items():
            for reading in readings:
                temptable.append(reading.current)
    elif wmisupport == True:
        print("Using WMI to grab temps...")
        RelaunchAsAdmin()
        w = wmi.WMI(namespace="root\wmi")
        sensors = w.MSAcpi_ThermalZoneTemperature()
        for sensor in sensors:
            temptable.append(round(sensor.CurrentTemperature / 10 - 273.15, 2))
    temperature = sum(temptable) / len(temptable)
    return temperature

def GetCurrentProcessInformation():
    starter = "process information for HOSTNAME at TIME".replace("HOSTNAME",platform.node()).replace("TIME",str(datetime.now()))
    totalinfo = [starter, "name - pid - status - user - exe location - command line params", "N/A shown when information couldn't be collected", "##################################################################################"]
    pids = psutil.pids()
    for pid in pids:
        try:
            processname = psutil.Process(pid).name()
        except psutil.NoSuchProcess:
            processname = "N/A"
        except psutil.AccessDenied:
            processname = "N/A"
        try:
            processexe = psutil.Process(pid).exe()
        except psutil.NoSuchProcess:
            processexe = "N/A"
        except psutil.AccessDenied:
            processexe = "N/A"
        try:
            processcmdline = psutil.Process(pid).cmdline()
            processcmdline = " ".join(processcmdline)
        except psutil.NoSuchProcess:
            processcmdline = "N/A"
        except psutil.AccessDenied:
            processcmdline = "N/A"
        try:
            processstatus = psutil.Process(pid).status()
        except psutil.NoSuchProcess:
            processstatus = "N/A"
        except psutil.AccessDenied:
            processstatus = "N/A"
        try:
            processuser = str(psutil.Process(pid).username())
        except psutil.NoSuchProcess:
            processuser = "N/A"
        except psutil.AccessDenied:
            processuser = "N/A"
        string = processname+" - "+str(pid)+" - "+processstatus+" - "+processuser+" - "+processexe+" - "+processcmdline
        totalinfo.append(string)
        #print(string) # debugging purposes only. for the love of god don't enable this.
    return totalinfo

def ConvertTimeToReasonableUnit(valueInSeconds, withUnit):
    if valueInSeconds > 60:
        valueInSeconds = valueInSeconds / 60
        unit = " minutes"
        if valueInSeconds > 60:
            valueInSeconds = valueInSeconds / 60
            unit = " hours"
            if valueInSeconds > 24:
                valueInSeconds = valueInSeconds / 24
                unit = " days"
            if valueInSeconds > 7:
                valueInSeconds = valueInSeconds / 7
                unit = " weeks"
                if valueInSeconds > 52.17857:
                    valueInSeconds = valueInSeconds / 52.17857
                    unit = " years"
    else:
        unit = " seconds"

    if withUnit == True:
        return str(round(valueInSeconds))+unit
    else:
        return valueInSeconds

def ConvertStorageToReasonableUnit(valueInBytes, withUnit):
    if valueInBytes > 1000: 
        valueInBytes = valueInBytes / 1000 #kb
        unit = "KB"
        if valueInBytes > 1000: 
            valueInBytes = valueInBytes / 1000 #mb
            unit = "MB"
            if valueInBytes > 1000: 
                valueInBytes = valueInBytes / 1000 #gb
                unit = "GB"
                if valueInBytes > 1000:
                    valueInBytes = valueInBytes / 1000 #tb
                    unit = "TB"
    else:
        unit = "B"

    if withUnit == True:
        return str(round(valueInBytes,2))+unit 
    else:
        return valueInBytes

def PrepareMessage():
    pubip = requests.get("https://icanhazip.com")
    if pubip.status_code == 200:
        print("Successfully grabbed public IP, showing in message.")
        pubip = pubip.text.replace('\n','')
    else:
        print("Failed to grab public IP. Status code: "+str(pubip.status_code))
        pubip = "(couldn't obtain)"

    with open(config['general']['script'],"r") as script:
        message = script.read()
    
    if config["stats"]["hostname"] == True:
        message = message.replace("HOSTNAME", platform.node(),1)
    else:
        message = message.replace("HOSTNAME", "<disabled in config>")
    if config["stats"]["platform"] == True:
        message = message.replace("PLATFORM", platform.platform(),1)
    else:
        message = message.replace("PLATFORM", "<disabled in config>")
    if config["stats"]["architecture"] == True:
        message = message.replace("ARCHITECTURE", platform.machine(),1)
    else:
        message = message.replace("ARCHITECTURE", "<disabled in config>")
    if config["stats"]["clockspeed"] == True:
        message = message.replace("CLOCKSPEED", str(round(psutil.cpu_freq().current)),1)
    else:
        message = message.replace("CLOCKSPEED", "<disabled in config>")
    if config["stats"]["username"] == True:
        message = message.replace("USERNAME", os.getlogin(),1)
    else:
        message = message.replace("USERNAME", "<disabled in config>")
    if config["stats"]["localip"] == True:
        message = message.replace("LOCALIPADDRESS", socket.gethostbyname(platform.node()),1)
    else:
        message = message.replace("LOCALIPADDRESS", "<disabled in config>")
    if config["stats"]["publicip"] == True:
        message = message.replace("PUBLICIPADDRESS", pubip,1)
    else:
        message = message.replace("PUBLICIPADDRESS", "<disabled in config>")
    if config["stats"]["pythonversion"] == True:
        message = message.replace("PYTHONVERSION", platform.python_version(),1)
    else:
        message = message.replace("PYTHONVERSION", "<disabled in config>")
    if config["stats"]["time"] == True:
        message = message.replace("TIME", str(datetime.now()),1)
    else:
        message = message.replace("TIME", "<disabled in config>",1)
    if config["stats"]["cpuusage"] == True:
        message = message.replace("CPUUSAGE", str(psutil.cpu_percent()),1)
    else:
        message = message.replace("CPUUSAGE", "<disabled in config>")
    if config["stats"]["ramusage"] == True:
        message = message.replace("RAMUSAGE", str(psutil.virtual_memory().percent),1) 
    else:
        message = message.replace("RAMUSAGE", "<disabled in config>")
    if config["stats"]["uploadrate"] == True:
        message = message.replace("UPLOADRATE", GetNetworkRate(False, True)+"/s")
    else:
        message = message.replace("UPLOADRATE", "<disabled in config>")
    if config["stats"]["downloadrate"] == True:
        message = message.replace("DOWNLOADRATE", GetNetworkRate(True, True)+"/s")
    else:
        message = message.replace("DOWNLOADRATE", "<disabled in config>")
    if config["stats"]["ramused"] == True:
        message = message.replace("RAMUSED", str(ConvertStorageToReasonableUnit(psutil.virtual_memory().used, True)),1)
    else:
        message = message.replace("RAMUSED", "<disabled in config>")
    if config["stats"]["ramfree"] == True:
        message = message.replace("RAMFREE", str(ConvertStorageToReasonableUnit(psutil.virtual_memory().free, True)),1)
    else:
        message = message.replace("RAMFREE", "<disabled in config>")
    if config["stats"]["ramtotal"] == True:
        message = message.replace("RAMTOTAL", str(ConvertStorageToReasonableUnit(psutil.virtual_memory().total, True)),1)
    else:
        message = message.replace("RAMTOTAL", "<disabled in config>")
    if config["stats"]["processcount"] == True:
        message = message.replace("PROCESSCOUNT", str(len(psutil.pids())),1)
    else:
        message = message.replace("PROCESSCOUNT", "<disabled in config>")
    if config["stats"]["uptime"] == True:
        message = message.replace("UPTIME", ConvertTimeToReasonableUnit((psutil.time.time() - psutil.boot_time()), True),1)
    else:
        message = message.replace("UPTIME", "<disabled in config>")
    if config["stats"]["lastboottime"] == True:
        message = message.replace("LASTBOOT", str(datetime.fromtimestamp(psutil.boot_time())),1)
    else:
        message = message.replace("LASTBOOT", "<disabled in config>")
    if config["stats"]["uploadbytes"] == True:
        message = message.replace("UPLOADBYTES", ConvertStorageToReasonableUnit(psutil.net_io_counters().bytes_sent, True),1)
    else:
        message = message.replace("UPLOADBYTES", "<disabled in config>")
    if config["stats"]["downloadbytes"] == True:
        message = message.replace("DOWNLOADBYTES", ConvertStorageToReasonableUnit(psutil.net_io_counters().bytes_recv, True),1)
    else:
        message = message.replace("DOWNLOADBYTES", "<disabled in config>")
    #print(message)

    if config["general"]["gpu"] == True:
        message = message+"\n \n"+"\n".join(GetGPUInformation())

    if config["general"]["newstorageinfo"] == True:
        message = message+"\n \n"+"\n".join(GetDriveUsageStats())
    elif config["general"]["newstorageinfo"] == False:   
        storetotal, storeused, storefree = shutil.disk_usage(__file__)
        message = message+"\n \n"+"Primary storage drive - "+str(round(((storeused / storetotal) * 100),1))+"% usage, "+ConvertStorageToReasonableUnit(storeused, True)+" used, "+ConvertStorageToReasonableUnit(storefree, True)+" free, "+ConvertStorageToReasonableUnit(storetotal, True)+" total"
        directories = config.get("general", {}).get("extradirectories", {})
        if not directories:
            print("No extra directories specified")
        else:
            for dir_name, path in directories.items():
                if path:
                   dir = os.path.abspath(os.path.normpath(path))
                   if not os.path.exists(dir):
                      print("Path "+dir+" doesn't exist")
                   else:
                    storetotal, storeused, storefree = shutil.disk_usage(dir)
                    message = message+"\n"+dir+" - "+str(round(((storeused / storetotal) * 100),1))+"% usage, "+ConvertStorageToReasonableUnit(storeused, True)+" used, "+ConvertStorageToReasonableUnit(storefree, True)+" free, "+ConvertStorageToReasonableUnit(storetotal, True)+" total"
                else:
                   print(f"{dir_name} has no path specified in config")

    if config['general']['temperature'] == True:
        message = message + "\n \n Average temperature: "+str(round(GetTemperatures(),2))+"℃"

    with open(os.path.join(scriptdir, "processlog.txt"), "w") as proclog:
        for info in GetCurrentProcessInformation():
            proclog.write(info + "\n")

    return message

while config["schedule"]["schedule"] == True:
    Distribute(PrepareMessage())
    print("Sent status report, waiting "+str(config["schedule"]["interval"])+" minute(s) before next report...")
    time.sleep(config["schedule"]["interval"]*60)

if config["schedule"]["schedule"] == False:
    Distribute(PrepareMessage())
    raise SystemExit()