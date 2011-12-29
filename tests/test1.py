from nose.tools import eq_
from vm_ut.dec_nose import on_vm, add_lxc_vm, ALL_VMS, add_kvm_vm

import module

#add_lxc_vm('oneiric', '/home/koder/vm_images/ut_lxc', 'root:root@192.168.122.2')
add_kvm_vm('debian', '/home/koder/vm_images/debian_lenny_amd64_standard_base.qcow2', 'root:root@192.168.122.2')
#add_kvm_vm('oneiric', '/home/koder/vm_images/debian_lenny_amd64_standard_base.qcow2', 'root:root@192.168.122.2')

#vm = ALL_VMS['debian']
#vm.conn = libvirt.open("qemu:///system")
#vm.start()

#def test_add():
#    print "execute"
#    eq_(module.add(1, 2), 3) 
#

#@dec_nose.decorator_vm_ut('oneiric', '192.168.122.2', "root", 'root')
#def test_sub():
#    print "start test"
#    eq_(module.sub(2, 1), 1)
#    print "finish test"
    

#def test_wrong_add():
#    eq_(module.add(2, 1), 1)

@on_vm('debian', use_existed=True)
def test_wrong_local():
    eq_(module.sub(4, 1), 1)

