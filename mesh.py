"""Simple program to demo how to use meshtastic library.
   To run: python examples/pub_sub_example2.py
"""

import time
import requests
import json

from pubsub import pub

import meshtastic
import meshtastic.serial_interface


sent_ssids = []




serial_id = '/dev/serial/by-id/usb-1a86_USB_Single_Serial_576D027276-if00'
kismet_user = 'sigsec'
kismet_url = 'http://{user}:{password}@localhost:2501'
kismet_url = kismet_url.format(user = kismet_user, password = "L0gg3r1!")
kismet_ssid_url = kismet_url+'/phy/phy80211/ssids/views/ssids.json'
kismet_device_url = kismet_url+'/devices/by-key/{DEVICEKEY}/device.json'
kismet_recent_devices = kismet_url+'/devices/last-time/{TIMESTAMP}/devices.json'

def getSSIDs():
    res = json.loads(requests.get(kismet_ssid_url).text)
    ssids = {i['dot11.ssidgroup.ssid']: i["dot11.ssidgroup.advertising_devices"] for i in res}
    return ssids

def getDevice(DEVICEKEY):
    url = kismet_device_url.format(DEVICEKEY = DEVICEKEY)
    res = json.loads(requests.get(url).text)
    return res

helptext = ['!ssid - send new ssid beacons',
'!clear - clear sent ssids',
'!devs [seconds=30] - get mac addresses active in last X seconds',
'!probes [seconds=30] - get probed ssids active in last X seconds',
'!find [mac1] [mac2]... - find last appearances of certain macs',
'!stu [mac] [field] - get arbitrary device field from a mac'
]

def onReceive(packet, interface):  # pylint: disable=unused-argument
    """called when a packet arrives"""
    print(packet)
    global sent_ssids

    message = ''
    if 'text' in packet['decoded'].keys():
        message = packet['decoded']['text'].lower().split(' ')
    else:
        return

    if message[0] == '!tskt':
        for line in helptext:
            iface.sendText(line)
    if message[0] == '!ssid':
        sent_ssids = scanSSIDs(sent_ssids)
    if message[0] == '!clear':
        del sent_ssids
    if message[0] == '!devs':
        if len(message) == 1:
            ts = f'{(time.time() - 30):.5f}'
        elif message[1] == 'all':
            ts = 0
        else: 
            ts = f'{(time.time() - float(message[1])):.5f}'
        devs = activeDevices(ts)
        for i in range(0, len(devs), 10):
            print(i)
            iface.sendText(' '.join(devs[i:i+10]))
    if message[0] == '!probes':
        if len(message) == 1:
            ts = f'{(time.time() - 30):.5f}'
        elif message[1] == 'all':
            ts = 0
        else: 
            ts = f'{(time.time() - float(message[1])):.5f}'
        probes = activeProbes(ts)
        for i in range(0, len(probes), 10):
            print(i)
            iface.sendText(' '.join(probes[i:i+10]))
    if message[0] == '!find':
        if len(message) >= 2:
            macs = message[1:]
            results = queryDevice(macs)
            results = [[i['kismet.device.base.macaddr'], i['kismet.device.base.last_time'], i['kismet.device.base.signal']['kismet.common.signal.last_signal']] for i in results]
            for result in results:
                print(','.join(result))
                iface.sendText(','.join(result))
    if message[0] == '!stu':
        if len(message) > 2:
            value = stu_its_three_am(message[1], message[2])
            if value:
                iface.sendText(str(value))
    pass


def onConnection(interface, topic=pub.AUTO_TOPIC):  # pylint: disable=unused-argument
    """called when we (re)connect to the radio"""
    # defaults to broadcast, specify a destination ID if you wish
    print('connected')

def setup():
    pub.subscribe(onReceive, "meshtastic.receive")
    pub.subscribe(onConnection, "meshtastic.connection.established")
    iface = meshtastic.serial_interface.SerialInterface()
    iface.sendText('xxxBEGIN TSKTxxx')
    return iface

def scanSSIDs(sent_ssids):
    current_ssids = getSSIDs()
    for ssid in list(set(current_ssids).difference(sent_ssids)):
        dev = ''
        if current_ssids[ssid]:
            DEVKEY = current_ssids[ssid][0]
            dev = getDevice(DEVKEY)["kismet.device.base.signal"]["kismet.common.signal.last_signal"]
        iface.sendText(ssid+' '+str(dev))
        sent_ssids.append(ssid)
    return sent_ssids

def activeDevices(fromTime):
    res = json.loads(requests.get(kismet_recent_devices.format(TIMESTAMP = fromTime)).text)
    macs = [i['kismet.device.base.macaddr'] for i in res]
    return macs

def activeProbes(fromTime):
    devs = []
    res = json.loads(requests.get(kismet_recent_devices.format(TIMESTAMP = fromTime)).text)
    for i in res:
        x = getDevice(i['kismet.device.base.key'])
        if 'dot11.device' in i.keys():
            if 'dot11.device.probed_ssid_map' in i['dot11.device'].keys():
                dev_probes = []
                for ssid in i['dot11.device']['dot11.device.probed_ssid_map']:
                    if ssid['dot11.probedssid.ssidlen']:
                        probe_name = ssid['dot11.probedssid.ssid']
                        dev_probes.append(probe_name)
                if dev_probes:
                    devs.append([i['kismet.device.base.macaddr'], dev_probes])
    return devs

def queryDevice(mac):
    url = kismet_url+f'/devices/multimac/devices.json'

    payload = {
        "devices": mac
    }
    
    try:
        response = requests.post(
            url,
            json=payload,
        )
        response.raise_for_status()  # Raise exception for HTTP errors
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return None

def search_json(json_obj, target_key):
    # First, check if current obj has the key
    if target_key in json_obj:
        return json_obj[target_key]
    # Else, iterate through values
    for value in json_obj.values():
        # Check if value is a dict or list
        if isinstance(value, dict):
            result = search_json(value, target_key)
            if result is not None:
                return result
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    result = search_json(item, target_key)
                    if result is not None:
                        return result
    # If not found anywhere, return None
    return None

def stu_its_three_am(mac, key):
    print(key)
    result = queryDevice([mac])
    if result:
        value = search_json(result[0], key)
        if value:
            return value
        else:
            return 'no key'
    else:
        return 'no device'

iface = setup()
print('interface up')
while True:
    #sent_ssids = scanSSIDs(sent_ssids)
    #if len(sent_ssids) > last_len:
    #    print(len(sent_ssids))
    #    last_len = len(sent_ssids)
    time.sleep(5)