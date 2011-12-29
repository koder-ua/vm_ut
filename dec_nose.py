# documentations

import os
import sys

try:
    import json
except ImportError:
    import simplejson as json

import socket
import pickle
import functools
import subprocess
import threading
import random

from nose.tools import ok_

try:
    from vm import KVM, LXC
except:
    KVM = LXC = None

from utils import get_logger

#from socket_logger import logger
logger = get_logger("dec_nose")

ALL_VMS = {}

def wait_ex(sock, cont, put_exc_here):
    sock.listen(1)
    sock.settimeout(0.01)
    conn = None
    
    while cont[0]:
        try:
            conn, _addr = sock.accept()
        except socket.timeout:
            pass

    #print "cont[0] =", cont[0]
    
    if conn is not None:
        conn.settimeout(10)
        exc = []
        
        c_exc = conn.recv(1000)
        
        while c_exc:
            exc.append(c_exc)
            c_exc = conn.recv(1000)
        
        conn.close()
        sock.close()
        exc = pickle.loads("".join(exc))
        put_exc_here.append(exc)

def add_lxc_vm(name, fname, credentials):
    if LXC is not None:
        vm = LXC(name, fname)
        vm.credentials = credentials
        ALL_VMS[name] = vm

def add_kvm_vm(name, fname, credentials):
    if KVM is not None:
        vm = KVM(name, fname)
        vm.credentials = credentials
        ALL_VMS[name] = vm

class VMUTDecorator(object):
    """
    decorator for executing test remotely on virtual machine
    creating subprocess for execiting test - function
    merge remote .coverage file with the existing
    """
    
    spliter = "----------------------------------------------------------------------"
    exc_addr = ['192.168.122.1', 50000]
    max_tryes = 15
    
    def __init__(self,
                 vm_name,
                 use_existed=False):
        '''
        @param vm_name: Name of the vm
        @type vm_name: string
        @param credentials:  user name, password, host ip 
        @type credentials: string, for example 'root:root@192.168.122.2'
        @param python: vertion of python on vm
        @type python: string
        '''
        self.python = 'python'
        self.remote_dir = '/tmp/ut'
        self.use_existed = use_existed
        self.vm_name = vm_name

    def bind_socket(self):
        ex_wait_sock = socket.socket()
        
        exc_addr = self.exc_addr[:]

        addr_used = True
        tryes = 0

        while addr_used and (tryes < self.max_tryes):
            try:
                tryes += 1
                ex_wait_sock.bind(tuple(exc_addr))
                addr_used = False
            except socket.error, exc:
                exc_addr[1] += int(random.random()*100)

            if tryes == self.max_tryes:
                raise RuntimeError("Can not start socket")
            
        return ex_wait_sock, tuple(exc_addr)

    def __call__(self, func):
        '''
        run test func on vm
        '''
        logger.debug("Decorator called. UNDER_VM={0}".format(os.environ.get('UNDER_VM', '0')))
        
        if os.environ.get('UNDER_VM', '0') == '1':
            return self.under_vm_decorator(func)
        else:
            return self.on_host_decorator(func)

    def under_vm_decorator(self, func):
        def cl2():
            try:
                logger.debug("return UT func")
                return func()
            except Exception, exc:
                host_port = os.environ.get('EXC_ADDR', None)
                if host_port is not None:
                    sock = socket.socket()
                    host, port = host_port.rsplit(':', 1)
                    sock.connect((host, int(port)))
                    sock.send(pickle.dumps(exc))
                    sock.close()
                raise
        return cl2

    def on_host_decorator(self, func):
        @functools.wraps(func)
        def closure(*args, **kwargs):

            func_name = func.__name__
            file_name = sys.modules[func.__module__].__file__                                                  
            exc_here = []
            cont = [True]

            self.ex_wait_sock, exc_addr = self.bind_socket()
          
            th = threading.Thread(None, wait_ex, None, (self.ex_wait_sock,
                                                        cont, exc_here))
            th.daemon = True
            th.start()

            vm = ALL_VMS[self.vm_name]
                
            params = {
                      'func_name' : func_name,
                      'vm_name'   : vm.name,
                      'file_name' : file_name,
                      'credentials' : vm.credentials,
                      'vm_type'   : vm.type_,
                      'vm_image' : vm.img_file,
                      'remote_dir': self.remote_dir,
                      'exc_addr'  : exc_addr,
                      'use_existed' : self.use_existed
                    }

            test_cmd = [self.python, "-m", "vm_ut.test_executor", json.dumps(params)]
            logger.debug("Start subprocess, {0}".format(" ".join(test_cmd)))

            proc = subprocess.Popen(test_cmd,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT)
            while True:
                dt = proc.stdout.read(1)
                if '' == dt:
                    break
                sys.stderr.write(dt)
            
            cont[0] = False
            th.join()
            
            if exc_here != []:
                raise exc_here[0]
                
        return closure

# some comment
on_vm = VMUTDecorator
