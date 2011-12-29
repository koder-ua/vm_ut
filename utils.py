import os
import sys
import logging
import subprocess
import contextlib

from nose.tools import ok_

loggers = {}

def get_logger(name):
    try:
        return loggers[name]
    except KeyError:
        log = logging.getLogger(name)

        # I HATE JAVA!!!

        log.setLevel(logging.DEBUG)

        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)

        fh = logging.FileHandler("/tmp/logs.txt")
        fh.setLevel(logging.DEBUG)

        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        fh.setFormatter(formatter)

        log.addHandler(ch)
        log.addHandler(fh)

        loggers[name] = log
        return log

logger = get_logger("utils")

def shell_exec(cmd):
    logging.info("Excecute {0!r}".format(cmd))

    out = subprocess.check_output(cmd, shell=True)
    logging.debug(out)
    return out

@contextlib.contextmanager
def cd(path):
    curr_dir = os.path.abspath(os.getcwd())
    os.chdir(path)
    logger.debug("cd " + path)
    try:
        yield None
    finally:
        os.chdir(curr_dir)


def ok():
    '''
    Return message-result of successful test-executing
    '''
    ok_(True)
    

def fail(msg):
    '''
    Return message-result of unsuccessful test-executing
    '''
    ok_(False, msg)


