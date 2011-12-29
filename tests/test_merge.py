import sys

sys.path.append('/home/user/workspace/axcient/axcient/UnitTests/vm_ut')

import merge

from nose.tools import ok_, eq_, raises
from mock import patch, Mock


merge.SSHCMDExecutor = Mock()
@patch("merge.os")
@patch("__builtin__.open", Mock())
class TestClassMerge(object):
    
    def test_merge_lists(self, *dt):
        obj = merge.CovMerge('192.168.122.2', 'root', 'root')
        list1 = [1,2,3]
        list2 = [4,5,6]
        list_merge = [1,2,3,4,5,6]
      
        list_func_merged = obj.merge_lists(list2, list1)
        eq_(list_func_merged, list_merge)

    def test_merge_lists_repeat_el(self, *dt):
        obj = merge.CovMerge('192.168.122.2', 'root', 'root')
        list1 = [1,2,3,3]
        list2 = [4,5,6,3]
        list_merge = [1,2,3,4,5,6]
        
        list_func_merged = obj.merge_lists(list2, list1)
        
        eq_(list_func_merged, list_merge)

    def test_merge_dicts(self, *dt):
        obj = merge.CovMerge('192.168.122.2', 'root', 'root')
        dict1 = {'1': [11, 12, 13],
                 '2': [21, 22, 23],
                 '3': [31, 32, 33]}
        dict2 = {'1': [14, 15, 16],
                 '4': [41, 42, 43],
                 '5': [51, 52, 53]}
        dict_merge = {'1': [11, 12, 13, 14, 15, 16],
                      '2': [21, 22, 23],
                      '3': [31, 32, 33],
                      '4': [41, 42, 43],
                      '5': [51, 52, 53]}
        
        dict_func_merged = obj.merge_dicts(dict2, dict1)        
        
        assert dict_func_merged == dict_merge
        
    def merge_files(self):
        pass
    
    def test_merge_to_exist_no_cur_cov(self, os_mock):
        os_mock.path.exists.return_value = False
        cov = merge.CovMerge()
        cov.ssh = Mock()
        cov.ssh.get_fl.return_value = "?????????? ?????"
        
    def test_merge_to_exist(self, *dt):
        os_mock.path.exists.return_value = True



#@patch("vm_ut.merge.os")
#@patch("__builtin__.open", Mock())
#def test_...(os_mock):
#    os_mock.path.exists.return_value = True
    
#    cov = m.CovMerge()
#    cov.ssh = Mock()
#    cov.ssh.get_fl.return_value = "?????????? ?????"

#    cov.merge_to_exist(...)