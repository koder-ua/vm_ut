'''
Created on Nov 3, 2011

@author: user
'''
import os
from nose.tools import ok_, eq_, raises
from vm_utils.cmd_executor import SSHCMDExecutor 
from vm import VM

vmname = "oneiric"
vmuser = "root"
vmpass = "root"
some_dir = "test_dir"      

def test_vm_starts():
    """
    starts vm
    creates folder on it with ssh
    and checks
    """
    vm = VM("oneiric")
    with vm.start():
        cmd = SSHCMDExecutor(vm.ip, vmuser, vmpass)
        cmd.exec_simple('mkdir /%s' % some_dir)
        tdirname = os.path.join(vm.fs.mpoint, some_dir)
        ok_(os.path.exists(tdirname))

def test_vm_rollbacks_after_test1():
    vm = VM("oneiric")
    with vm.start():
        tdirname = os.path.join(vm.fs.mpoint, some_dir)
        SSHCMDExecutor(vm.ip, vmuser, vmpass)
        ok_(not os.path.exists(tdirname))