#!/usr/bin/env python3

from __future__ import with_statement

import os
import sys
import errno
import argparse
import code
import pprint
import json

from fusepy import FUSE, FuseOSError, Operations
from boxsdk import OAuth2, Client

TOKENS_DIR="./tokens"
TOKENS_FILE=TOKENS_DIR+"/tokens"
APP_CLIENTID="rbowlcj4sc7u96dfxprgd26bhqwt5nlz"
APP_SECRET="Huiq0x7vxFgKjpAlp9k0WAcLxQ1Efmjh"
APP_ACCESS_TOKEN=""
LOGFILE='/tmp/fs.log'

class BoxFuseFS(Operations):
    def __init__(self):
        self.root = "/code"
        self.log('Starting')

    # Helpers
    # =======

    def _full_path(self, partial):
        if partial.startswith("/"):
            partial = partial[1:]
        path = os.path.join(self.root, partial)
        return path

    def log(self,message):
        l = open(LOGFILE,'a')
        l.write(message+'\n')
        l.close()
        pass

    # Filesystem methods
    # ==================

    def access(self, path, mode):
        full_path = self._full_path(path)
        if not os.access(full_path, mode):
            raise FuseOSError(errno.EACCES)

    def chmod(self, path, mode):
        full_path = self._full_path(path)
        return os.chmod(full_path, mode)

    def chown(self, path, uid, gid):
        full_path = self._full_path(path)
        return os.chown(full_path, uid, gid)

    def getattr(self, path, fh=None):
        self.log("getattr " +path)
        full_path = self._full_path(path)
        st = os.lstat(full_path)
        return_val = dict((key, getattr(st, key)) for key in ('st_atime', 'st_ctime', 
            'st_gid', 'st_mode', 'st_mtime', 'st_nlink', 'st_size', 'st_uid'))
        self.log("getattr " +path+ "\n"+pprint.pformat(return_val))
        return return_val

    def readdir(self, path, fh):
        self.log("readdir " +path)
        full_path = self._full_path(path)

        dirents = ['.', '..']
        if os.path.isdir(full_path):
            dirents.extend(os.listdir(full_path))
        for r in dirents:
            yield r

    def readlink(self, path):
        self.log("readlink " +path)
        pathname = os.readlink(self._full_path(path))
        if pathname.startswith("/"):
            # Path name is absolute, sanitize it.
            return os.path.relpath(pathname, self.root)
        else:
            return pathname

    def mknod(self, path, mode, dev):
        return os.mknod(self._full_path(path), mode, dev)

    def rmdir(self, path):
        full_path = self._full_path(path)
        return os.rmdir(full_path)

    def mkdir(self, path, mode):
        return os.mkdir(self._full_path(path), mode)

    def statfs(self, path):
        self.log("statfs " +path)
        full_path = self._full_path(path)
        stv = os.statvfs(full_path)
        return dict((key, getattr(stv, key)) for key in ('f_bavail', 'f_bfree',
            'f_blocks', 'f_bsize', 'f_favail', 'f_ffree', 'f_files', 'f_flag',
            'f_frsize', 'f_namemax'))

    def unlink(self, path):
        return os.unlink(self._full_path(path))

    def symlink(self, name, target):
        return os.symlink(name, self._full_path(target))

    def rename(self, old, new):
        return os.rename(self._full_path(old), self._full_path(new))

    def link(self, target, name):
        return os.link(self._full_path(target), self._full_path(name))

    def utimens(self, path, times=None):
        return os.utime(self._full_path(path), times)

    # File methods
    # ============

    def open(self, path, flags):
        self.log("open " +path)
        full_path = self._full_path(path)
        return os.open(full_path, flags)

    def create(self, path, mode, fi=None):
        full_path = self._full_path(path)
        return os.open(full_path, os.O_WRONLY | os.O_CREAT, mode)

    def read(self, path, length, offset, fh):
        self.log("read " +path+" length: "+length+ " offset: "+offset)
        os.lseek(fh, offset, os.SEEK_SET)
        return os.read(fh, length)

    def write(self, path, buf, offset, fh):
        os.lseek(fh, offset, os.SEEK_SET)
        return os.write(fh, buf)

    def truncate(self, path, length, fh=None):
        full_path = self._full_path(path)
        with open(full_path, 'r+') as f:
            f.truncate(length)

    def flush(self, path, fh):
        self.log("flush " +path)
        return os.fsync(fh)

    def release(self, path, fh):
        self.log("release " +path)
        return os.close(fh)

    def fsync(self, path, fdatasync, fh):
        self.log("fsync " +path)
        return self.flush(path, fh)


def main(mountpoint):
    FUSE(BoxFuseFS(), mountpoint, nothreads=True, foreground=True)


def store_tokens(access_token, refresh_token):
    # store the tokens at secure storage (e.g. Keychain)
    print ("store token\naccess_token: "+access_token+"\nrefresh_token:"+refresh_token)
    data = { "access_token": access_token,
            "refresh_token": refresh_token
    }
    with open(TOKENS_FILE, "w") as write_file:
        json.dump(data, write_file)


def authenticate_with_box():
    print ("Authenticate with box")
    client = None
    oauth = OAuth2(
        client_id=APP_CLIENTID,
        client_secret=APP_SECRET,
        store_tokens=store_tokens,
    )

    auth_url, csrf_token = oauth.get_authorization_url('https://github.com/r00k135/boxfusefs/wiki/authenticated')
    print ("Navigate to this URL in a browser: "+auth_url)
    auth_code = input("Type the value from the result URL and the code= parameter in here: ")
    APP_ACCESS_TOKEN, refresh_token = oauth.authenticate(auth_code)    
    return oauth


if __name__ == '__main__':
    # Check parameters
    parser = argparse.ArgumentParser(description='Box.com Fuse Filesystem')
    parser.add_argument('mountpoint', metavar="mountpoint", help='mountpoint')
    args = parser.parse_args()
    # print (args)
    # check .tokens directory exists
    if os.path.exists(TOKENS_DIR) == False:
        try:
            os.makedirs(TOKENS_DIR)
        except OSError:
            print ("unable to create "+TOKENS_DIR+" directory")
            exit (1)
    # See if token file exists
    oauth = None
    client = None
    if os.path.isfile(TOKENS_FILE):
        print ("Loading saved access_token")
        with open(TOKENS_FILE) as data_file:    
            data = json.load(data_file)
            #print (pprint.pprint(data))
            try:
                APP_ACCESS_TOKEN = data["access_token"]
                oauth = OAuth2(APP_CLIENTID, APP_SECRET, access_token=APP_ACCESS_TOKEN)
            except:
                oauth = authenticate_with_box()  
    else:
       oauth = authenticate_with_box() 

    print ("Starting client")
    client = Client(oauth)
    me = client.user(user_id='me').get()
    print ('user_login: ' + me['login'])
    main(args.mountpoint)
    code.interact(local=locals())