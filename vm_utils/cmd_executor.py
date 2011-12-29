import os
import errno
import fcntl
import select
import signal
import logging
import subprocess

import paramiko

plogger = paramiko.util.get_logger('paramiko.transport')
plogger.setLevel(logging.ERROR)

class CMDExecutor(object):
    """Base implementation for local and SSH command executions"""
    def __init__(self):
        """Preconfigure class"""
        self.last_result = None
        self.last_stdout = None
        self.stdin = None

    def getLastResult(self):
        """get last results"""
        if self.last_result is None:
            raise RuntimeError("no last result available")
        return self.last_result

    def execute(self,**cmd):
        """Execute command pure virtual func"""
        raise RuntimeError("Pure virtual fucntion call")

    def exec_simple_check(self,*cmd):
        """Execute command and check ret code"""
        res = self.exec_simple(*cmd)

        assert 0 == res, "Cmd %r exited with code %s. Output: %r" \
                        % (cmd, self.last_result, self.last_stdout)

    def exec_simple(self,*cmd):
        """execute command without checking return code"""
        stdout = []

        for i in self.execute(*cmd):
            stdout.append(i)

        self.last_stdout = "".join(stdout)

        return self.last_result

    def send(self, data):
        """Send data to command stdin"""
        self.stdin.write(data)
        self.stdin.flush()


class SSHCMDExecutor(CMDExecutor):
    """Class implements command execution over SSH"""
    def __init__(self, host, username, password, port=22, timeout = None):
        """Store SSH parameters"""
        super(SSHCMDExecutor,self).__init__()
        self.ssh = paramiko.SSHClient()
        self.ssh.load_system_host_keys()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh.connect(host, port=int(port), 
                               username=username, 
                               password=password, 
                               allow_agent=False,
                               timeout = timeout)

    def __del__(self):
        self.close()

    def close(self):
        if self.ssh is not None:
            self.ssh.close()
            self.ssh = None

    def __enter__(self):
        return self

    def __exit__(self, x, y, z):
        self.close()
        
    def execute(self,*cmd):
        """Execute command over SSH"""
        self.chan = self.ssh.get_transport().open_session()
        try:
            self.chan.setblocking(False)

            self.chan.exec_command(" ".join(cmd))

            outs = {'out':"",'err':""}

            continue_loop = True
            while continue_loop:

                if self.chan.exit_status_ready():
                    continue_loop = False

                try:
                    select.select([self.chan], [], [], 0.1)
                except:
                    continue

                while self.chan.recv_ready():
                    outs['out'] += self.chan.recv(10280)

                while self.chan.recv_stderr_ready():
                    outs['err'] += self.chan.recv_stderr(10280)

                for key,data in outs.items():

                    lns = data.split('\n')

                    for dt in lns[:-1]:
                        yield dt + "\n"

                    outs[key] = lns[-1]


            for i in outs.values():
                if i != "":
                    yield i

            self.last_result = self.chan.recv_exit_status()
        finally:
            self.chan.close()
            self.chan = None

    @classmethod
    def connect(cls, url, *dt, **mp):
        user_passwd, host_port = url.split('@')
        user, passwd = user_passwd.split(':',1)
        
        if ':' in host_port:
            host,port = host_port.split(':')
        else:
            port = 22
            host = host_port
        
        return cls(host, user, passwd, port, *dt, **mp)


class LocalCMDCanceled(Exception):
    """Raised when CMD canceled"""
    pass


class LocalCMDExecutor(CMDExecutor):
    """Class implements local command execution"""

    # If set to True all current unsafe commands are interrupted,
    # all future unsafe commands raise LocalCMDCanceled exception
    cancel = False





    def __init__(self, set_new_group=False, safe=False, env=None, cwd=None):
        """Create a LocalCMDExecutor object
        @param set_new_group: whether execute child process in new group
                              (default - False)
        @type set_new_group: bool
        @param safe: safe commands can be executed after cancel_all,
                     these commands will not hang and can be used for cleanup
        @type safe: bool
        @param env: environment for child process
        @type env: dict
        """

        super(LocalCMDExecutor, self).__init__()

        self.safe = safe
        self.signal_sent = False
        if self.cancel and not self.safe:
            raise LocalCMDCanceled()

        self.set_new_group = set_new_group
        self.nowait = False

        self.env = env
        self.cwd = cwd

    @classmethod
    def cancel_all(cls):
        """Cancel current and all future local unsafe cmds"""
        cls.cancel = True

    def set_nowait(self, nowait):
        """If nowait is set to True execute() will yield
        empty string if no data is in stdout"""
        self.nowait = nowait

    def _set_nonblock(self, stream):
        """Set O_NONBLOCK flag for given stream"""
        fdesc = stream.fileno()
        flags = fcntl.fcntl(fdesc, fcntl.F_GETFL)
        fcntl.fcntl(fdesc, fcntl.F_SETFL, flags | os.O_NONBLOCK)

    def execute(self, *cmd):
        """Execute command locally"""

        self.last_result = None

        if self.set_new_group:
            preexec_fn = os.setsid
        else:
            preexec_fn = None

        self.proc = subprocess.Popen(cmd,
                             stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT,
                             close_fds=True,
                             preexec_fn=preexec_fn,
                             env=self.env,
                             cwd=self.cwd)
        proc = self.proc
        self.pid = self.proc.pid
        self.pgid = os.getpgid(self.proc.pid)

        logger.debug("New cmd with pid {0} : {1}".format(self.pid,
                                                         " ".join(cmd)))

        self._set_nonblock(proc.stdout)

        self.stdin = proc.stdin

        for i in self.deferred:
            self.stdin.write(i)
        self.deferred = []

        try:
        
            while True:
                try:
                    if self.cancel and not self.signal_sent and not self.safe:
                        # do not send signal second time
                        self.signal_sent = True
                        if self.set_new_group:
                            self.send_signal_to_group(signal.SIGTERM)
                        else:
                            self.send_signal(signal.SIGTERM)

                    dt = proc.stdout.read()
                    if dt == '':
                        break
                    #logger.debug("Output from pid: {0} {1}".format(self.pid,dt))
                    yield dt
                except IOError:
                    # EWOULDBLOCK

                    if self.nowait:
                        yield ''

                    try:
                        select.select([proc.stdout], [], [], 1)
                    except select.error:
                        # select.error: (4, 'Interrupted system call') - ignore it,
                        # just call select again
                        pass

            self.wait_proc_finished(proc)

            if self.signal_sent:
                raise LocalCMDCanceled(list(cmd), self.last_result)

        finally:
            self.stdin = None

    def wait_proc_finished(self, proc):
        # wait proc finished
        while True:
            try:
                proc.wait()
                self.last_result = proc.returncode
                break
            except OSError, e:
                if e.errno == errno.EINTR:
                    # Interrupted system call
                    continue
                elif e.errno == errno.ECHILD:
                    # Somebody has already called waitpid
                    break
                else:
                    raise

    def send_signal(self, signal=signal.SIGTERM):
        """Send signal to command being executed"""
        self.proc.send_signal(signal)

    def send_signal_to_group(self, signal=signal.SIGTERM):
        """Send signal to the process group
        of the command being executed"""
        os.killpg(self.pgid, signal)

    def __repr__(self):
        try:
            return "Cmd with pid %d" % self.pid
        except AttributeError:
            return "Cmd not started"

