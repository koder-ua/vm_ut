#!/usr/bin/env python
from __future__ import with_statement

import re
import glob
import time
import Queue
import socket
import threading
import xml.etree.ElementTree as etree

import ipaddr
import libvirt

from vm_utils.utils import flatten
from xmlbuilder import XMLBuilder
from vm_utils.cmd_executor import SSHCMDExecutor

from vm_utils.network import get_next_mac, get_ips_for_hws
from devices import Device, ETHDevice, ETHNetworkDevice, ETHBridgedDevice,\
                       HDDBlockDevice, HDDFileDevice, FileSystemDevice

#suppress libvirt error messages to console
libvirt.registerErrorHandler(lambda x,y : 1, None)

class DomainConfig(object):
    def __init__(self, name, memory, vcpu, devices):
        self.name = name
        self.memory = memory
        self.vcpu = vcpu
        self.devices = devices
        

class virDomainEx(libvirt.virDomain):
    
    if_re = re.compile("inet addr:(?P<ip>(?:\d{1,3}\.){3}\d{1,3})")

    KVM = 'kvm'
    XEN = 'xen'
    LXC = 'lxc'

    domain_type = None
    emulator_path = None
    
    def __init__(self, *dt, **mp):
        # faked code for pylint only
        libvirt.virDomain.__init__(self, *dt, **mp)
        self.etree = None
        self.memory = None
        self.vcpu = None
        self.devices = None
        self.name = None
        self.persistent = None

    @classmethod
    def construct(cls, conn, persistent, name, memory, vcpu, *devices):
        etree = cls.makeXML(name, memory, vcpu, *devices)
        
        if conn.__class__ is libvirt.virConnect:
            self = conn.createXML(str(etree), 0)
        else:
            self = conn.createXMLWithType(str(etree), 0, cls.domain_type)
            
        self.__class__ = cls
        
        self.etree = etree
        self.memory = memory
        self.vcpu = vcpu
        self.devices = devices
        self.name = name
        self.persistent = persistent
        
        return self
        
    @classmethod
    def fromVirDomain(cls, domain):
        domxml = etree.fromstring(domain.XMLDesc(0))

        find = domxml.find
        findall = domxml.findall
        find_text = lambda path : find(path).text.strip()
        
        domain.__class__ = cls
        
        if domain.__class__ is libvirt.virDomain:
            raise libvirt.libvirtError("Domain type %r isn't supported by libvirtex" %
                               domain)
            
        domain.etree = domxml
        
        domain.memory = int(find_text('memory'))
        domain.vcpu = int(find_text('vcpu'))
        
        domain.devices = []

        for device_class in [ETHNetworkDevice, ETHBridgedDevice,
                       HDDBlockDevice, HDDFileDevice, FileSystemDevice]:
            domain.devices.extend(device_class.fromxml(findall))

        domain.name = find_text('name')
        domain.persistent = True
        
        return domain
    
    def toXML(self):
        return self.makeXML(self.name, self.memory, self.vcpu, self.devices)
    
    @classmethod
    def commonFields(cls, root, config):
        root.name(config.name)
        root.memory(str(config.memory))
        root.uuid
        root.vcpu(str(config.vcpu))
    
    @classmethod
    def generateOS(cls, root, config):
        pass
    
    @classmethod
    def powerFeatures(cls, root, config):
        root.on_poweroff('destroy')
        root.on_reboot('restart')
        root.on_crash('destroy')
        
        with root.features:
            root.acpi
            root.hap
            root.apic
        
    @classmethod
    def emulator(cls, root, config):
        if cls.emulator_path is None:
            raise libvirt.libvirtError("Class %r has no emulator_path field" % cls)
        root.emulator(cls.emulator_path)

    @classmethod
    def commonDevices(cls, root, cfg):
                with root.serial(type='pty'):
                    root.target(port='0')
                
                with root.console(type='pty'):
                    root.target(port='0')
                
                root.input(bus='ps2', type='mouse')
                root.graphics(autoport='yes', 
                              keymap='en-us', 
                              type='vnc', 
                              port='-1')

    @classmethod
    def makeXML(cls, name, memory, vcpu, *devices):
        
        if cls.domain_type is None:
            raise libvirt.libvirtError("%r can't be instanciated - no domain type" \
                                % cls)
            
        
        cfg = DomainConfig(name, memory, vcpu, devices)
        
        root = XMLBuilder('domain', type=cls.domain_type)

        cls.commonFields(root, cfg)
                    
        with root.os:
            cls.generateOS(root, cfg)
        
        root.clock(sync='localtime')
        
        cls.powerFeatures(root, cfg)
        
        with root.devices:
            cls.emulator(root, cfg)
            
            for dev in devices: 
                dev.toxml(root)
            
            cls.commonDevices(root, cfg)

        return root
    
    def get_devices(self, tp = Device):
        for dev in self.devices:
            if isinstance(dev, tp):
                yield dev
    
    def __enter__(self):
        return self
    
    def __exit__(self, x, y, z):
        if not self.persistent:
            self.destroy()

    def get_ips(self):
        return [eth.ip for eth in self.eths(True) if eth.ip is not None]

    def eths(self, with_ip=False, conn=None, netmask=None):
        devs = list(self.get_devices(ETHDevice))
        
        if with_ip:
            no_ips = [dev for dev in devs if dev.ip is None]
            
            if no_ips:
                if netmask:
                    hw2ip = get_ips_for_hws(netmask,
                                            *[dev.hw for dev in no_ips])
                elif conn:
                    nmappings = {}
                    hw2ip = {}
                    
                    for dev in no_ips:
                        nmappings.setdefault(dev.network,[]).append(dev)
                
                    for network, curr_devs in nmappings.items():
                        net_xml = conn.networkLookupByName(network).XMLDesc()
                        
                        tag = etree.fromstring(net_xml).find('ip')
                        
                        addr = tag.attrib['address']
                        mask = tag.attrib['netmask']
                        
                        vir_netmask = str(ipaddr.IPNetwork(
                                        "{0}/{1}".format(addr, mask)))
                        
                        hw2ip.update(get_ips_for_hws(vir_netmask,
                                                *[dev.hw for dev in curr_devs]))
                
                for dev in no_ips:
                    dev.ip = hw2ip.get(dev.hw, None)

        return devs


class KVMDomain(virDomainEx):
    hvloader = '/usr/lib/xen-default/boot/hvmloader'
    
    domain_type = virDomainEx.KVM
    emulator_path = '/usr/bin/kvm'
    
    @classmethod
    def generateOS(cls, root, config):
        root.type('hvm')
        root.loader(cls.hvloader)
        root.boot(dev='hd')
        root.boot(dev='cdrom')
        root.bootmenu(enable='yes')
        root.bios(useserial='yes')


class LXCDomain(virDomainEx):

    domain_type = virDomainEx.LXC
    emulator_path = '/usr/lib/libvirt/libvirt_lxc'
    
    @classmethod
    def generateOS(cls, root, config):
        root.type('exe')
        root.init('/sbin/init')
    
    @classmethod
    def powerFeatures(cls, root, config):
        root.on_poweroff('destroy')
        root.on_reboot('restart')
        root.on_crash('destroy')

    @classmethod
    def commonDevices(cls, root, config):
        #root.console(type='pty')
        pass


class VMConnector(object):
    def __init__(self, vm):
        self.ssh_addr = None
        self.rpyc_addr = None
        self.rpyc_pem_file = None        
        self.ssh_user = None
        self.ssh_passwd = None
        self.vm = vm

    def set_ssh_credentials(self, user, passwd):
        self.ssh_user = user
        self.ssh_passwd = passwd
        
    def check_ips(self, func, cache_attr = None):
        
        if cache_attr is not None:
            val = getattr(self, cache_attr)
        else:
            val = None

        ips = set(self.vm.get_ips())
        
        if val is not None and val in ips:
            ips.remove(val)
            search_ips = (val,) + tuple(ips)
        else:
            search_ips = ips
        
        for ip in search_ips:
            try:
                res = func(ip)
                if cache_attr is not None:
                    setattr(self, cache_attr, ip)
                return res
            except socket.timeout:
                pass

    def wait_ssh_ready(self):
        while True:
            res = self.conn_ssh()

            if res is not None:
                return res

            time.sleep(1)
    
    def conn_ssh(self):
        def conn_ssh(ip):
            return SSHCMDExecutor(ip,
                                  self.ssh_user,
                                  self.ssh_passwd,
                                  timeout = 10)
        
        res = self.check_ips(conn_ssh, 'ssh_addr')
        return res
    
    def set_rpyc_pem_file(self, pem_file):
        self.rpyc_pem_file = pem_file
    
    def rpyc_start_server(self,
                          pem_file_path = '/opt/rpyc/cert.pem',
                          rpyc_server = '/opt/rpyc/rpyc_classic.py'):
        ssh_conn = self.conn_ssh()
        ssh_conn.exec_simple_check(("nohup python {0} --ssl-keyfile " + \
                                   "{1} --ssl-certfile {1} &").format(
                                        rpyc_server,
                                        pem_file_path))
        
    def conn_rpyc(self):
        import rpyc
        
        def conn_rpyc(ip):
            return rpyc.classic.ssl_connect(
                                    ip,
                                    keyfile = self.rpyc_pem_file,
                                    certfile = self.rpyc_pem_file)
        
        return self.check_ips(conn_rpyc, 'rpyc_addr')

class virConnectEx(libvirt.virConnect):
    uri_prefix = None
    vmClass = None
    
    def networkDev(self, network):
        netxml = self.networkLookupByName(network).XMLDesc(0)
        return etree.fromstring(netxml).find('bridge').attrib['name']

    def mkDomain(self, libvirtdomain):
        if self.vmClass is None:
            raise libvirt.libvirtError("%r can't create any domain" % \
                               self.__class__)
        return self.vmClass.fromVirDomain(libvirtdomain)
    
    def lookupByName(self, name):
        return self.mkDomain(libvirt.virConnect.lookupByName(self, name))
        
    def lookupByID(self, did):
        return self.mkDomain(libvirt.virConnect.lookupByID(self, did))
        
    def allDomains(self, name_filter = None):
        if name_filter is not None:
            nfl = lambda name : glob.fnmatch.fnmatchcase(name, name_filter)
        else:
            nfl = lambda name : True
        
        for domain_id in self.listDomainsID():
            dom = self.lookupByID(domain_id)
            if nfl(dom.name):
                yield dom
    
    def createXMLWithType(self, xml, val, dom_tp):
        if self.vmClass is None:
            raise libvirt.libvirtError("%r can't create any domain" % \
                               self.__class__)

        if dom_tp != self.vmClass.domain_type:
            raise libvirt.libvirtError("%r can't create domaint type %r" % \
                               (self.__class__, dom_tp))
        
        return self.createXML(xml, val)
    

class QEMUvirConnect(virConnectEx):
    uri_prefix = 'qemu://'
    vmClass = KVMDomain
    

class LXCvirConnect(virConnectEx):
    uri_prefix = 'lxc://'
    vmClass = LXCDomain


ALL_CONNECTIONS = [QEMUvirConnect, LXCvirConnect]
ALL_CONNECTIONS_MAP = {}

for conn in ALL_CONNECTIONS:
    ALL_CONNECTIONS_MAP[conn.uri_prefix] = conn
    
def open_libvirt(uri, *dt, **mp):
    conn = libvirt.open(uri, *dt, **mp)
    
    if not isinstance(conn.__class__, virConnectEx):
        for pref, cls in ALL_CONNECTIONS_MAP.items():
            if uri.startswith(pref):
                conn.__class__ = cls

    if not issubclass(conn.__class__, virConnectEx):
        raise libvirt.libvirtError("Can't find extended connection class for %r uri" \
                            % uri)
    
    return conn

class VirtConnectionProxy(object):
    def __init__(self, *uris):
        self.conns = []
        self.domain_map = {}
        
        for uri in uris:
            conn = open_libvirt(uri)
            self.conns.append(conn)
            self.domain_map[conn.vmClass] = conn

    def lookupByName(self, name):
        for conn in self.conns[:-1]:
            try:
                return conn.lookupByName(name)
            except libvirt.libvirtError:
                pass
        return self.conns[-1].lookupByName(name)
    
    def lookupByID(self, did):
        for conn in self.conns[:-1]:
            try:
                return conn.lookupByID(did)
            except libvirt.libvirtError:
                pass
        return self.conns[-1].lookupByID(did)
    
    def allDomains(self, name_filter = None):
        for conn in self.conns:
            for domain in conn.allDomains(name_filter):
                yield domain
    
    def networkDev(self, name):
        return self.conss[0].networkDev(name)
    
    def createXMLWithType(self, xml, val, domtp):
        for conn in self.conns:
            try:
                return conn.createXMLWithType(xml, val, domtp)
            except libvirt.libvirtError:
                pass
        raise libvirt.libvirtError(\
            "Can't find appropriate connection for %r domain type" % domtp)
        
        