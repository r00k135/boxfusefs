# boxfusefs
Box Fuse FileSystem - this filesystem allows you mount a box account as a fuse filesystem for read-only. I originally wrote it so that I could serve my home media collection via Kodi and using SMB seemed like a good idea. Although this filesystem works, it can't get the throughput to serve full 1080p video due to the inherent FUSE filesystem blocksize of 128K. Re-compiling the kernel fuse module seems a bit drastic.

## Install

git clone <this repo>

### Ubuntu
Install python3 and dependent modules
sudo apt-get install fuse libfuse-dev python3 python3-pip python3-fusepy 
pip3 install "boxsdk>=1.5,<2.0"

### Get API Information (I have already done this and hard-coded the App details)
Access Box Developer Portal and Create a new Custom App and use Standard Oauth 2.0: https://developer.box.com/docs/setting-up-an-oauth-app
Provides a "Client ID" and "Client Secret"


## Run (as non-root user)

./standalone.sh <mount>

First time you fun this will prompt you to log-in to box and ask you to authorise the app. This runs in the foreground so when you exit the process it unmounts the filesystem. To exit press CTRL-C and then it exits into an interactive python prompt, the press CTRL-D to exit completely.


## References

Urllib3: https://github.com/urllib3/urllib3
Box Python SDK: https://github.com/box/box-python-sdk
Box Python SDK Intro: http://opensource.box.com/box-python-sdk/tutorials/intro.html
Box API: https://developer.box.com/v2.0/reference


