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
import urllib3
import requests
import certifi

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

#http_pool = urllib3.HTTPConnectionPool(host='api.box.com', port=443, maxsize=20,
#    cert_reqs='CERT_REQUIRED',
#    ca_certs=certifi.where(),
#    assert_same_host=False)

http_pool_headers = urllib3.make_headers(
    keep_alive=True, 
    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/68.0.3440.106 Safari/537.36"
    )
#http_pool_api = urllib3.connection_from_url('https://api.box.com',
#    cert_reqs='CERT_REQUIRED',
#    ca_certs=certifi.where(),
#    headers=http_pool_headers,
#    maxsize=10,
#    block=False)

#http_pool_dl = urllib3.connection_from_url('https://dl.boxcloud.com',
#    cert_reqs='CERT_REQUIRED',
#    ca_certs=certifi.where(),
#    headers=http_pool_headers,
#    maxsize=10,
#    block=False)

http_pool_mgr = urllib3.PoolManager(10,
    headers=http_pool_headers,
    block=False)

start_time = time.time()
folder_cache = { 
    '/': {
        'boxid': 0,
        'type': 'folder',
        'st_size': 4096,
        'st_atime': start_time,
        'st_ctime': start_time,
        'st_mtime': start_time,
        'st_ino': 0,
        'st_dev': 0,
        'st_gid': GID,
        'st_mode': stat.S_IFDIR | 0o777,
        'st_nlink': 2,
        'st_uid': UID
    }
}
redirect_cache = {}


class BoxFuseFS(Operations):
    def __init__(self):
        self.log('Starting')

    # Helpers
    # =======

    def log(self,message):
        l = open(LOGFILE,'a')
        l.write(message+'\n')
        l.close()
        pass

    # Filesystem methods
    # ==================

    def access(self, path, mode):
        self.log("access " +path)
        return 0

    def chmod(self, path, mode):
        self.log("chmod " +path+" access denied")
        raise FuseOSError(errno.EACCES)
        return 0

    def chown(self, path, uid, gid):
        self.log("chown " +path+" access denied")
        raise FuseOSError(errno.EACCES)
        return 0

    def getattr(self, path, fh=None):
        self.log("getattr " +path)
        if path != "/" and len(folder_cache) == 1:
            self.log("getattr " +path+ " first read of root")
            self.populateFolderCache("/")
        if path in folder_cache:
            if 'st_size' in folder_cache[path]:
                return_val = folder_cache[path]
                self.log("getattr "+path+" "+pprint.saferepr(return_val))
                return return_val
            else:
                self.log("getattr boxid: "+str(folder_cache[path]["boxid"]))
                file_query = client.file(folder_cache[path]["boxid"]).get()
                folder_cache[path]["st_size"] = file_query["size"]
                folder_cache[path]["st_ctime"] = time.mktime(time.strptime(file_query["created_at"], "%Y-%m-%dT%H:%M:%S-07:00"))
                folder_cache[path]["st_mtime"] = time.mktime(time.strptime(file_query["modified_at"], "%Y-%m-%dT%H:%M:%S-07:00"))
                folder_cache[path]["st_atime"] = time.time()
                return_val = folder_cache[path]
                self.log("getattr " +path+ " "+pprint.saferepr(return_val))
                return return_val
        else:
            # Not in cache, try populateFolderCache one direcory up
            oneback = path.split("/")
            oneback.pop()
            oneback.reverse()
            oneback.pop()
            oneback.reverse()
            self.log("getattr " +path+ " oneback: "+pprint.saferepr(oneback))
            if len(oneback) > 0:
                searchpath = ""
                for element in oneback:
                    searchpath += "/"+element
                self.log("getattr " +path+ " searchpath: "+searchpath)
                self.populateFolderCache(searchpath)
                if path in folder_cache:
                    return_val = folder_cache[path]
                    self.log("getattr " +path+ " "+pprint.saferepr(return_val))
                    return return_val
                else:
                    self.log("getattr " +path+ " ENOENT (Not Found) - folder not found")
                    raise FuseOSError(errno.ENOENT)
                    return {}
            else:
                self.log("getattr " +path+ " ENOENT (Not Found) - oneback empty")
                raise FuseOSError(errno.ENOENT)
                return {}

    def populateFolderCache(self, path):
        self.log("populateFolderCache " +path)
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
            #self.log("readdir item "+str(item))
            fileItem = folder_query[item]
            newPath = translated_path+"/"+fileItem["name"]
            folder_cache[newPath] = dict()
            if fileItem["type"] == "folder":
                folder_cache[newPath]['st_size'] = 4096
                folder_cache[newPath]['st_mode'] = stat.S_IFDIR | 0o777
                folder_cache[newPath]['st_nlink'] = 2
            if fileItem["type"] == "file":
                folder_cache[newPath]['st_size'] = fileItem["size"]
                folder_cache[newPath]['st_mode'] = stat.S_IFREG | 0o777
                folder_cache[newPath]['st_nlink'] = 1
            folder_cache[newPath]["boxid"] = fileItem["id"]
            folder_cache[newPath]["type"] = fileItem["type"]
            folder_cache[newPath]["st_atime"] = start_time
            folder_cache[newPath]["st_ctime"] = time.mktime(time.strptime(fileItem["created_at"], "%Y-%m-%dT%H:%M:%S-07:00"))
            folder_cache[newPath]["st_mtime"] = time.mktime(time.strptime(fileItem["modified_at"], "%Y-%m-%dT%H:%M:%S-07:00"))
            folder_cache[newPath]["st_gid"] = GID
            folder_cache[newPath]["st_uid"] = UID
            folder_cache[newPath]["st_ino"] = 0
            folder_cache[newPath]["st_dev"] = 0
            dirents.append(fileItem["name"]) 
            item = item + 1
        self.log("populateFolderCache " +path+ " dirents: "+pprint.pformat(dirents))
        return dirents

    def readdir(self, path, fh=None):
        self.log("readdir " +path)
        dirents = self.populateFolderCache(path)
        for r in dirents:
            yield r

    def readlink(self, path):
        self.log("readlink " +path)
        return path

    def mknod(self, path, mode, dev):
        return 0

    def rmdir(self, path):
        self.log("rmdir " +path+" access denied")
        raise FuseOSError(errno.EACCES)
        return 0

    def mkdir(self, path, mode):
        self.log("mkdir " +path+" access denied")
        raise FuseOSError(errno.EACCES)
        return 0

    def statfs(self, path):
        self.log("statfs " +path)
        return {
            'f_bavail': 0,
            'f_bfree:': 0,
            'f_blocks': 4,
            'f_bsize': 1024,
            'f_favail': 0,
            'f_ffree': 0,
            'f_files': 1,
            'f_frsize': 512,
            'f_namelen': 255
        }

    def unlink(self, path):
        self.log("unlink " +path+" access denied")
        raise FuseOSError(errno.EACCES)
        return 0

    def symlink(self, name, target):
        self.log("symlink " +path+" access denied")
        raise FuseOSError(errno.EACCES)
        return 0

    def rename(self, old, new):
        self.log("rename " +path+" access denied")
        raise FuseOSError(errno.EACCES)
        return 0

    def link(self, target, name):
        self.log("link " +path+" access denied")
        raise FuseOSError(errno.EACCES)
        return 0

    def utimens(self, path, times=None):
        return 0

    # File methods
    # ============

    def open(self, path, flags):
        self.log("open " +path)
        return 0

    def create(self, path, mode, fi=None):
        self.log("create " +path+" access denied")
        raise FuseOSError(errno.EACCES)
        return 0

    def read(self, path, length, offset, fh):
        self.log("read " +path+" length: "+str(length)+ " offset: "+str(offset))
        boxid = folder_cache[path]["boxid"]
        data = ""
        headers = { 
            'Authorization': 'Bearer '+oauth.access_token, 
            'Range': 'bytes='+str(offset)+"-"+str(offset+(length-1)), 
            'Connection': 'keep-alive', 
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/68.0.3440.106 Safari/537.36' 
            }
        start_time = time.time()
        if path in redirect_cache:
            self.log("read " +path+" redirect cached")
        else:
            self.log("read " +path+" getting redirect")
            r_api = http_pool_mgr.request('GET', 'https://api.box.com/2.0/files/'+str(boxid)+'/content', headers=headers, redirect=False)
            redirect_cache[path] = r_api.headers["Location"]
            #r_api.release_conn()
        r_dl = http_pool_mgr.request('GET', redirect_cache[path], headers=headers, preload_content=False)
        data = r_dl.read()
        #r_dl.release_conn()
        # get end time
        end_time = time.time()
        elapsed_time = end_time - start_time
        self.log("read " +path+" ELAPSED: "+str(round(elapsed_time, 4)))
        return data

    def write(self, path, buf, offset, fh):
        os.lseek(fh, offset, os.SEEK_SET)
        return os.write(fh, buf)

    def truncate(self, path, length, fh=None):
        return 0

    def flush(self, path, fh):
        self.log("flush " +path)
        return 0

    def release(self, path, fh):
        self.log("release " +path)
        return 0

    def fsync(self, path, fdatasync, fh):
        self.log("fsync " +path)
        return self.flush(path, fh)


def main(mountpoint):
    FUSE(BoxFuseFS(), mountpoint, nothreads=False, foreground=True, allow_other=True, max_readahead=262144, max_read=262144)


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
    # Populate root directory
    main(args.mountpoint)
    code.interact(local=locals())