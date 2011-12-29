import os
import sys
import uuid

try:
    import json
except ImportError:
    import simplejson as json

import time
import shutil
import os.path
import subprocess

import paramiko

from vm import is_ssh_ready, LXC, KVM
from utils import get_logger, cd
from cmd_executor import SSHCMDExecutor
from libvirtex.connection import VirtConnectionProxy

logger = get_logger("test_excutor")

def merge_lists(lst, lst_merge_to):
    '''
    merge two lists without repeat of the elements
    '''
    st = set(lst)
    st_merge_to = set(lst_merge_to)
    st_merge_to = st_merge_to.union(st)
    ret_val = list(st_merge_to)
    ret_val.sort()
    return ret_val
    

def merge_dicts(dct, dct_merge_to):
    '''
    merge two dicts without repeat of the elements.
    if key alredy exist in the list - merging values without
    repeat of the elements.
    else - add key and value to the dict
    '''

    for k, v in dct.iteritems():
        if k in dct_merge_to.keys():
            dct_merge_to[k] = merge_lists(v, dct_merge_to[k])
        else:
            dct_merge_to[k] = v

    return dct_merge_to
            
def merge_files(data, fname_marge_to):
    '''
    if there is no file .coverage on the current machine
    create file .coverage
    '''
    fd = os.open(fname_marge_to, os.O_RDWR|os.O_CREAT)
    os.write(fd,data)
    os.close(fd)
            
def merge_cov_file(fc1, fc2):
    dct = pickle.loads(fc1)['lines']
    dct_merge_to = pickle.loads(fc2)['lines']
    
    merged_dct = self.merge_dicts(dct, dct_merge_to)
    
    final_dct = pickle.loads(fc1)
    final_dct['lines'] = merged_dct
    return pickle.dumps(final_dct)

def copy_remote_files(path_to_vm, local, remote):
    '''
    copy files from the current machine to the remote one
    Before copy - rm remote tree
    '''
    if path_to_vm.startswith('ssh://'):
        user_passwd, ip = path_to_vm[len('ssh://'):].split('@', 1)
        
        if '+' in ip:
            ip, port = ip.split('+')
        else:
            port = 22
            
        user, passwd = user_passwd.split(':', 1)
        fname = str(uuid.uuid1()) + '.tgz'
        out_fl = "/tmp/" + fname

        with cd(os.path.dirname(local)):
            subprocess.check_call("tar cvzf {0} {1}".format(out_fl, 
                                                            os.path.basename(local)), shell=True)

        t = paramiko.Transport((ip, port))
        t.connect(username=user, password=passwd, hostkey=None)
        sftp = paramiko.SFTPClient.from_transport(t)
        
        try:
            rfl = os.path.join(remote, fname)
            logger.debug("Write {0} => {1}".format(out_fl, rfl))
            fl = sftp.open(rfl, "wb")
            fl.write(open(out_fl, 'rb').read())
            fl.close()
        finally:
            t.close()

        ssh = SSHCMDExecutor(ip, user, passwd, port=port)
        ssh.exec_simple_check('''cd {0} ; tar xfz {1}'''.format(remote, rfl))
        ssh.exec_simple_check('cd {0} ; rm ' + rfl)
        
    else:
        rpath = os.path.join(path_to_vm, remote[1:])
        
        try:
            shutil.rmtree(rpath)
        except:
            pass
        
        shutil.copytree(local, rpath)
        
        fake_dec_path = os.path.dirname(sys.modules[ExecTest.__module__].__file__)
        fake_dec_path = os.path.join(fake_dec_path,"..")
        fake_dec_rpath = os.path.join(rpath, "UnitTests")
        shutil.copytree(fake_dec_path, fake_dec_rpath)
    logger.debug("file tree copied to remote machine")
  
    
    
class ExecTest(object):
    """
    Class implements executing of the
    unit test on the remote vm
    in the new process
    with merging of .coverage
    """
    def __init__(self, file_name, 
                       func_name, 
                       exc_addr, 
                       vm_type, 
                       vm_name, 
                       credentials, 
                       remote_dir,
                       vm_image, 
                       use_existed):
        '''
        @param file_name: name of the file which contain executing function
        @type file_name: string
        @param func_name: name of the executing function
        @type func_name: string
        @param vm_name: name of the vm
        @type vm_name: string
        @param credentials:  user name, password, host ip 
        @type credentials: string, for example 'root:root@192.168.122.2'
        @param remote_dir: name of the remote dir
        @type remote_dir: string
        '''
        user_password, self.hostip = credentials.rsplit('@', 1)
        self.user, self.password = user_password.split(':', 1)
        
        self.local_dir, self.file_name = os.path.split(file_name)
        self.use_existed = use_existed
        
        use_libvirt = ('0' == os.environ.get("NOT_USE_LIBVIRT", '0'))
            
        if use_libvirt:
            self.conn = VirtConnectionProxy('lxc://', 'qemu:///system')
        else:
            self.conn = None
        
        if vm_type == 'lxc':
            self.vm = LXC(vm_name,
                             vm_image,
                             ip=self.hostip,
                             destroy_on_exit=True,
                             conn=self.conn)
        elif vm_type == 'kvm':
            self.vm = KVM(vm_name,
                             vm_image,
                             ip=self.hostip,
                             destroy_on_exit=True,
                             conn=self.conn)
        else:
            raise ValueError("Unknown vm type " + vm_type)

        self.vm_name = vm_name
        self.func_name = func_name
        self.remote_dir = remote_dir
        self.exc_addr = exc_addr
        self.credentials = credentials

    def do_test(self):
        '''
        Exec test on the remote vm
        Start VM
        Copy files to vm
        Exec cm to run the test
        Get .coverage from VM
        Merge remot file with existing .coverage 
        '''
        logger.debug("Try to start VM")
        if not self.use_existed:
            with self.vm.start():
                self._do_test()
        else:
            self._do_test()
    
    def _do_test(self):
        for i in range(30):
            if is_ssh_ready(self.hostip):
                break
            time.sleep(1)
    
        if not is_ssh_ready(self.hostip):
            raise RuntimeError("Can't connect to vm")

        logger.debug("VM started")

        if self.vm.type_ == 'lxc':
            path = self.vm.fs.mpoint
        else:
            path = "ssh://" + self.credentials

        ssh = SSHCMDExecutor(self.hostip, self.user, self.password)

        cmd = 'mkdir -p "{0}"'.format(self.remote_dir)
        logger.debug(cmd)
        ssh.exec_simple(cmd)

        
        logger.debug("copy file tree to remote machine {1} => {0} + {2}".format(path, self.local_dir, self.remote_dir))
        copy_remote_files(path, self.local_dir, self.remote_dir)

        logger.debug("copy ut module code to vm {1} => {0} + {2}".format(path, os.path.dirname(__file__), self.remote_dir))
        copy_remote_files(path, os.path.dirname(__file__), self.remote_dir)

        
        cmd = (''' sh -c 'cd {0}; env PYTHONPATH="{0}:/tmp/ut/unit_test" UNDER_VM=1 ''' + \
                '''EXC_ADDR="{3}:{4}" nosetests -v --cover-erase ''' + \
                '''--with-coverage {1}:{2}' ''')\
                    .format(self.remote_dir,
                            os.path.splitext(self.file_name)[0],
                            self.func_name,
                            self.exc_addr[0],
                            self.exc_addr[1])
        
        logger.debug("Executing comand " + cmd)
        
        ssh.exec_simple(cmd)
        
        logger.debug("Get remote .coverage file " + os.path.join(self.remote_dir, '.coverage'))

        remote_cov_fl = ssh.get_fl(os.path.join(self.remote_dir, '.coverage'))

        local_fpath = os.path.join(self.local_dir, '.coverage')

        if exists(local_fpath):
            local_cov_fl = open(local_fpath, 'rb').read()
            new_cov_fl = merge_cov_file(local_cov_fl, remote_cov_fl)
        else:
            new_cov_fl = remote_cov_fl
        
        open(os.path.join(self.local_dir, '.coverage'), 'wb').write(new_cov_fl)

def main(**mp):
    logger.debug("Test executor starts")
    ex = ExecTest(**mp)
    ex.do_test()

if __name__ == '__main__':
    sys.exit(main(**json.loads(sys.argv[1])))    

    
    
    
