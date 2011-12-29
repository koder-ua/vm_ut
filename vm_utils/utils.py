import re
import Queue
import types
import threading


def tmap(func, params_list, auto_raise=True):
    res_q = Queue.Queue()

    def th_func(param):
        try:
            res_q.put((True, param, func(param)))
        except Exception, x:
            res_q.put((False, param, x))
            
    for val in params_list:
        th = threading.Thread(None, th_func, None, (val,))
        th.daemon = True
        th.start()
    
    th = None
    
    for _ in range(len(params_list)):
        ok, param, res = res_q.get()
        if not ok:
            raise res
        else:
            yield ok, param, res

need_flatten = lambda val : isinstance(val, (list, tuple, types.GeneratorType))

def flatten(val, flat_check = need_flatten):
    res = []
    for i in val:
        if flat_check(i):
            res.extend(flatten(i))
        else:
            res.append(i)
    return res

ip_re = re.compile(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}")
ip_host = re.compile(
    r"^(?P<ip>\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s+(?P<hosts>.*)$")

def parse_hosts(hosts_content):
    for ln in hosts_content.split('\n'):
        mr = ip_host.match(ln.strip())
        if mr:
            ip = mr.group('ip')
            all_hosts_str = mr.group('hosts')
            all_hosts = [host for host in all_hosts_str.split(' ') if host]
            yield True, (ip, all_hosts)
        else:
            yield False, ln

def hosts_remove_host(hosts_content, host_name):
    for is_ip, obj in parce_hosts(hosts_content):
        if not is_ip:
            yield obj
        else:
            ip, hosts = obj
            hosts = [host for host in hosts if host != host_name]
            yield " ".join([ip] + hosts)

def hosts_remove_ip(hosts_content, ip):
    for is_ip, obj in parce_hosts(hosts_content):
        if not is_ip:
            yield obj
        else:
            found_ip, hosts = obj
            if ip != found_ip:
                hosts.insert(0, ip)
                yield " ".join(hosts)
    
def hosts_add_hostip(hosts_content, host_name, ip):
    for is_ip, obj in parce_hosts(hosts_content):
        if not is_ip:
            yield obj
        else:
            found_ip, hosts = obj
            if ip != found_ip:
                hosts = [host for host in hosts if host != host_name]
                hosts.insert(0, ip)
                yield " ".join(hosts)
    yield ip + " " + host_name

    
    
    
    
    
    
    