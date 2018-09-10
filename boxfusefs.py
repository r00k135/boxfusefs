#!/usr/bin/env python3

from __future__ import with_statement

import os
import sys
import errno
import argparse
import code
import pprint
import json
import stat
import fuse
import fusepy
import time

from fusepy import FUSE, FuseOSError, Operations
from boxsdk import OAuth2, Client

TOKENS_DIR="./tokens"
TOKENS_FILE=TOKENS_DIR+"/tokens"
APP_CLIENTID="rbowlcj4sc7u96dfxprgd26bhqwt5nlz"
APP_SECRET="Huiq0x7vxFgKjpAlp9k0WAcLxQ1Efmjh"
APP_ACCESS_TOKEN=""
LOGFILE='/tmp/fs.log'
UID=os.geteuid()
GID=os.getgid()

start_time = time.time()
folder_cache = { 
    '/': {
        'boxid': 0,
        'type': 'folder',
        'st_size': 4096,
        'st_atime': start_time,
        'st_ctime': start_time,
        'st_mtime': start_time,
        'st_gid': GID,
        'st_mode': stat.S_IFDIR | 0o555,
        'st_nlink': 2,
        'st_uid': UID
    }
}


class MyStat(fusepy.c_stat):
    def __init__(self):
        self.st_mode = stat.S_IFDIR | 0o755
        self.st_ino = 0
        self.st_dev = 0
        self.st_nlink = 2
        self.st_uid = 0
        self.st_gid = 0
        self.st_size = 4096
        self.st_atime = 0
        self.st_mtime = 0
        self.st_ctime = 0

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
        #st = MyStat()
        #pe = path.split('/')[1:]

        #st.st_atime = int(time())
        #st.st_mtime = st.st_atime
        #st.st_ctime = st.st_atime
        #return_val = dict((st))
        #self.log("getattr " +path+ "\n"+pprint.pformat(return_val))
        #return return_val
        if path in folder_cache:
            if 'st_size' in folder_cache[path]:
                return_val = folder_cache[path]
                self.log("getattr " +path+ "\n"+pprint.pformat(return_val))
                return return_val
            else:
                self.log("getattr boxid: "+str(folder_cache[path]["boxid"]))
                file_query = client.file(folder_cache[path]["boxid"]).get()
                folder_cache[path]["st_size"] = file_query["size"]
                folder_cache[path]["st_ctime"] = time.mktime(time.strptime(file_query["created_at"], "%Y-%m-%dT%H:%M:%S-07:00"))
                folder_cache[path]["st_mtime"] = time.mktime(time.strptime(file_query["modified_at"], "%Y-%m-%dT%H:%M:%S-07:00"))
                folder_cache[path]["st_atime"] = time.time()
                return_val = folder_cache[path]
                self.log("getattr " +path+ "\n"+pprint.pformat(return_val))
                return return_val

        else:
            return -errno.ENOSYS

        #full_path = self._full_path(path)
        #st = os.lstat(full_path)
        #self.log("getattr " +path+ "\n"+pprint.pformat(st))
        #return_val = dict((key, getattr(st, key)) for key in ('st_atime', 'st_ctime', 
        #    'st_gid', 'st_mode', 'st_mtime', 'st_nlink', 'st_size', 'st_uid'))
        #self.log("getattr " +path+ "\n"+pprint.pformat(return_val))
        #return return_val

    def readdir(self, path, fh):
        self.log("readdir " +path)
        full_path = self._full_path(path)
        folder_id = folder_cache[path]["boxid"]

        translated_path = ""
        if path != "/":
            translated_path = path

        dirents = ['.', '..']
        folder_query = client.folder(folder_id).get_items(limit=1000,fields=['id','size','type','created_at','modified_at','name'])
        length = int(len(folder_query))
        self.log("readdir " +path+" len: "+str(length))
        item = 0
        while item < length:
            fileItem = folder_query[item]
            newPath = translated_path+"/"+fileItem["name"]
            folder_cache[newPath] = dict()
            if fileItem["type"] == "folder":
                folder_cache[newPath]['st_size'] = 4096
                folder_cache[newPath]['st_mode'] = stat.S_IFDIR | 0o555
                folder_cache[newPath]['st_nlink'] = 2
            if fileItem["type"] == "file":
                folder_cache[newPath]['st_size'] = fileItem["size"]
                folder_cache[newPath]['st_mode'] = stat.S_IFREG | 0o555
                folder_cache[newPath]['st_nlink'] = 1
            folder_cache[newPath]["boxid"] = fileItem["id"]
            folder_cache[newPath]["type"] = fileItem["type"]
            folder_cache[newPath]["st_atime"] = start_time
            folder_cache[newPath]["st_ctime"] = time.mktime(time.strptime(fileItem["created_at"], "%Y-%m-%dT%H:%M:%S-07:00"))
            folder_cache[newPath]["st_mtime"] = time.mktime(time.strptime(fileItem["modified_at"], "%Y-%m-%dT%H:%M:%S-07:00"))
            folder_cache[newPath]["st_gid"] = GID
            folder_cache[newPath]["st_uid"] = UID
            self.log("readdir item "+str(item))
            dirents.append(fileItem["name"]) 
            item = item + 1
        #if os.path.isdir(full_path):
        #    dirents.extend(os.listdir(full_path))
        self.log("dirents " +path+ "\n"+pprint.pformat(dirents))
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
        #full_path = self._full_path(path)
        #return os.open(full_path, flags)
        return int(folder_cache[path]["boxid"])

    def create(self, path, mode, fi=None):
        full_path = self._full_path(path)
        return os.open(full_path, os.O_WRONLY | os.O_CREAT, mode)

    def read(self, path, length, offset, fh):
        self.log("read " +path+" length: "+str(length)+ " offset: "+str(offset)+" fh: "+str(fh))
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
    FUSE(BoxFuseFS(), mountpoint, nothreads=True, foreground=True, allow_other=True)


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
        print ("Loading saved access_token: "+TOKENS_FILE)
        with open(TOKENS_FILE) as data_file:    
            data = json.load(data_file)
            #print (pprint.pprint(data))
            try:
                APP_ACCESS_TOKEN = data["access_token"]
                APP_REFRESH_TOKEN = data["refresh_token"]
                oauth = OAuth2(APP_CLIENTID, APP_SECRET, access_token=APP_ACCESS_TOKEN, refresh_token=APP_REFRESH_TOKEN, store_tokens=store_tokens)
                #if (oauth.access_token != APP_ACCESS_TOKEN):

            except e:
                printf ("Error open tokens file: "+e)  
    else:
       oauth = authenticate_with_box() 

    print ("Starting client")
    client = Client(oauth)
    me = client.user(user_id='me').get()
    print ('user_login: ' + me['login'])
    main(args.mountpoint)
    code.interact(local=locals())