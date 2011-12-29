'''
Created on Oct 28, 2011

@author: user
'''

import os
import uuid

from utils import shell_exec, cd, get_logger

class IRestorableFS(object):
    """
       File system with commit and roolback
       Interface for the  fylesystems with rollback and commit
    """
    save_changes = False

    def __enter__(self):
        """for construction 'with :'"""
        pass

    def __exit__(self, type, value, traceback):
        if type != None:
            self.umount()

    def mount(self, mpoint):
        """mount fs"""
        return self

    def umount(self):
        """umount fs"""
        pass

    def commit(self):
        """commit changes on fs"""
        pass

class BtrFS(IRestorableFS):
    """Btrfs based implemantation of RestorableFS"""
    def __init__(self, device=None, image_file=None):
        self.save_changes = False
        self.device = device
        self.image_file = image_file
        self.snapname = None
        self.snappath = None
        self.subvolid = None

        assert self.image_file is not None or self.device is not None
        assert self.image_file is None or self.device is None

    def subvolumes(self):
        res = shell_exec('btrfs subvolume list "{0}"'.format(self.mpoint))
        for line in res.split('\n'):
            items = line.split(" ")
            #      subvolid  subvolpath
            yield items[1], items[6]
    
    def create_snapshot(self):
        self.snapname = str(uuid.uuid1())
        self.snappath = os.path.join(self.mpoint, 'snapshots', self.snapname)

        shell_exec('btrfs subvolume snapshot "{0}" "{1}"'.format(
                self.mpoint, self.mpoint))
        
        for subvolid, subvolume in self.subvolumes():
            if subvolume.endswith(self.snapname):
                break

        assert subvolume.endswith(self.snapname)
        self.subvolid = subvolid

    def remove_all_snapshot(self):
        for subvolid, subvolume in self.subvolumes():
            shell_exec('btrfs subvolume delete "{0}"'.format(
                    os.path.join(self.mpoint, subvolume)))

    def mount(self, mpoint):
        """
        mounts device than creates subvolume on this device umounts device
        and mounts snapshot in folder "mpoint"
        """

        if self.image_file is not None:
            if not os.path.exists(self.image_file):
                raise ValueError("FS file not found: {0!r}".format(
                    self.image_file))

            losetup = shell_exec('losetup -f --show "{0}"'.format(
                                self.image_file))
            self.device = losetup.split("\n")[0]

        self.mpoint = mpoint

        shell_exec('mount "{0}" "{1}"'.format(self.device, self.mpoint))
        
        self.create_snapshot()

        shell_exec('umount "{0}"'.format(self.mpoint))
        shell_exec('mount -o "subvolid={0}" "{1}" "{2}"'.format(
                                                self.subvolid, 
                                                self.device,
                                                self.mpoint))
        return self

    def umount(self):
        """
        umounts fs
        if method commit() was executed else makes working suvolume default
        (saves changes on disk), else deletes working subvolume (restores
        its state)
        """
        if self.save_changes:
            tdir = self.mpoint
        else:
            tdir = "/"
        
        with cd(tdir):
            if self.save_changes:
                shell_exec('btrfs subvolume set-default "{0}" "{1}"'.format(\
                                                                 self.snap,
                                                                 self.mpoint))
                self.save_changes = False
            else:
                shell_exec('umount "{0}"'.format(self.mpoint))
                shell_exec('mount "{0}" "{1}"'.format(self.device, self.mpoint))

                os.chdir(self.mpoint)

                shell_exec('btrfs subvolume delete "{0}"'.format(self.snap))
            
            os.chdir("/")
            shell_exec('umount "{0}"'.format(self.mpoint))

        if self.image_file is not None:
            shell_exec('losetup -d "{0}"'.format(self.device))
    

    def commit(self):
        """
            if this function used, changes on umount will be saved
        """
        self.save_changes = True

RestorableFS = BtrFS
