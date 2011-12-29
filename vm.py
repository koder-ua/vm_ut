import os
import uuid
import socket
import subprocess

from libvirtex.connection import LXCDomain, KVMDomain
from libvirtex.devices import FileSystemDevice, ETHNetworkDevice, HDDFileDevice
from vm_utils.cmd_executor import SSHCMDExecutor

from restorablefs import RestorableFS
from utils import shell_exec

class IVM(object):
    """
      Interface of class for working with container
    """
    def __init__(self, name, login, pwd):
        self.name = name

    def __enter__(self):
        pass

    def __exit__(self, type, value, traceback):
        #self.stop()
        pass

    def start(self):
        """starts container"""
        return self

    def get_ip(self):
        return self.ip

    def stop(self):
        """stops container"""
        pass


def is_ssh_ready(ip, port=22):
    """Checks is port opened on host with given ip """
    s = socket.socket()
    s.settimeout(0.1)
    try:
        s.connect((ip, port))
        return True
    except socket.error, x:
        return False


class KVM(IVM):
    type_ = 'kvm'
    def __init__(self,
                 name,
                 img_file,
                 ip="192.168.122.2",
                 hwaddr='4A:59:43:49:79:BF',
                 destroy_on_exit=True,
                 conn=None):
        """
        configures kvm based vm
        name - name of your vm
        you may change ip or hwaddr if you need
        """
        self.img_file = img_file

        if not os.path.exists(self.img_file):
            raise ValueError("Image file not found: %s" % self.img_file)

        self.name = name
        self.ip = ip
        self.hwaddr = hwaddr
        self.vm_file = None
        self.conn = conn

    def start(self):
        """starts container"""
        self.vm_file = "/tmp/{0}.qcow2".format(uuid.uuid1())
        
        shell_exec('qemu-img create -f qcow2 -b "{0}" "{1}"'.
                                format(self.img_file, self.vm_file))
        
        self.vm = KVMDomain.construct(self.conn,
                                      True,
                                      self.name,
                                      1024 * 1024,
                                      1,
                                      HDDFileDevice(self.vm_file,
                                                    type_='qcow2',
                                                    dev='hda',
                                                    bus='ide'),
                                      ETHNetworkDevice(self.hwaddr,
                                                       "vnet7",
                                                       ip=self.ip))
        return self

    def get_ip(self):
        return self.ip

    def stop(self):
        """stops container"""
        self.vm.destroy()
        os.unlink(self.vm_file)
    

class LXC(IVM):
    """Class for working with LXC based virtual machines"""
    type_ = 'lxc'
    def __init__(self,
                 name,
                 fs_file,
                 ip="192.168.122.2",
                 hwaddr='4A:59:43:49:79:BF',
                 destroy_on_exit=True,
                 conn=None,
                 lxc_name=None):
        """
        configures lxc based vm
        name -- name of your vm
        you may change ip or hwaddr if you need
        fs_file may be changed to your fs(btrfs) file
        """

        self.name = name
        self.ip = ip
        self.hwaddr = hwaddr
        self.img_file = fs_file

        self.fs = RestorableFS(image_file=fs_file)

        self.destroy_on_exit = destroy_on_exit
        self.use_libvirt = (conn != None)
        self.conn = conn
        self.lxc_name = lxc_name if lxc_name is not None else self.name

    def start(self, fs_mpoint_folder="/tmp/vms"):
        """
        starts lxc based vm
        fs_mpoint_folder is a folder where your vms file system
        will be mounted in some folder. It should exist
        """
        self.started = False
        
        if  not os.path.exists(fs_mpoint_folder):
            shell_exec('mkdir -p "{0}"'.format(fs_mpoint_folder))
        
        mpoint = os.path.join(fs_mpoint_folder, str(uuid.uuid1()))

        shell_exec('mkdir -p "{0}"'.format(mpoint))
        self.fs.mount(mpoint)
        
        try:
            if self.use_libvirt:
                self.vm = LXCDomain.construct(self.conn,
                                          True,
                                          self.name,
                                          1024 * 1024,
                                          2,
                                          FileSystemDevice(mpoint),
                                          ETHNetworkDevice(self.hwaddr,
                                                           "vnet7",
                                                           ip=self.ip))
            else:
                shell_exec('lxc-start -d -n "{0}"'.format(self.lxc_name))
        
        except:
            self.stop()
            raise
     
        logger.info("Domain started ok with ip {0!r} wait ssh ready".format(self.ip))
        
        for i in range(100):
            if is_ssh_ready(self.ip):
                self.started = True
                return self
        
        logger.critical("ssh failed to start on ip {0!r}".format(self.ip))
        self.stop()
        raise Exception("VM refuses to start")

    def stop(self):
        """Stops vm. Destroys changes on it """
        if self.destroy_on_exit:
            if self.started:
                if self.use_libvirt:                
                    self.vm.destroy()
                else:
                    shell_exec('lxc-stop -n "{0}"'.format(self.lxc_name))

            self.fs.umount()
            shell_exec('rm -rf "{0}"'.format(self.fs.mpoint))


