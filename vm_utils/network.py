import re
import os
import random
import socket
import threading
import subprocess

import ipaddr

from getall_ifs import localifs

ip_hwaddr_re = re.compile('(?P<ip>(?:\d{1,3}\.){3}\d{1,3})\s+(?P<hw>(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2})')
make_mak = '00:44:01:{0:02X}:{1:02X}:{2:02X}'.format
MAX_3B_NUM = 256 * 256 * 256 
now = random.randint(0,MAX_3B_NUM - 1)
mac_lock = threading.Lock()

def get_next_mac():
    global now
    while True:
        with mac_lock:
            now = (now + 1) % MAX_3B_NUM
            mnow = now
        yield make_mak((mnow & 0xFF0000) >> 16,
                    (mnow & 0xFF00) >> 8,
                    mnow & 0xFF)

def get_all_ips_arpscan(netmask, dev = None):
    
    net = ipaddr.IPNetwork(netmask)
    
    if dev is None:
        eths = []
        
        for name, ip in localifs():
            if ipaddr.IPAddress(ip) in net:
                eths.append(name)
    else:
        eths = [dev]
    
    for eth in eths:
        proc = subprocess.Popen(
                'arp-scan -I {0} {1}'.format(eth, netmask).split(),
               stdout = subprocess.PIPE,
               stderr = subprocess.STDOUT)
    
        proc.wait()
        
        res = []
        for i in proc.stdout.read().split('\n'):
            
            ip_hw_match = ip_hwaddr_re.match(i)
            
            if ip_hw_match:
                yield ip_hw_match.group('hw').upper(), ip_hw_match.group('ip')

def get_all_ips_dnsmasq(lease_file = "/var/lib/misc/dnsmasq.leases"):
    with open(lease_file) as fd:
        for line in fd:
            _, mac, ip = line.split(' ', 3)[:3]
            yield mac.upper(), ip

def get_ips_for_hws(netmask, *hws):
    
    map1 = dict(get_all_ips_dnsmasq())
    
    res = dict((hw, map1[hw]) for hw in hws if hw in map1)
    
    if len(res) == len(hws):
        return res
    
    if netmask is not None:
        map2 = dict(get_all_ips_arpscan(netmask))
    
    res.update(dict((hw, map2[hw]) for hw in hws if hw in map2))
    
    return res

def is_host_alive(ip):
    return os.system('ping -c 1 -W 1 {0} 2>&1 > /dev/null'.format(ip)) == 0
    
def is_ssh_ready(ip, port=22):
    s = socket.socket()
    s.settimeout(1)
    try:
        s.connect((ip, port))
        return True
    except socket.error, x:
        return False
