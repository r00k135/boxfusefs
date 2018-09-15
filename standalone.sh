#!/usr/bin/env bash

# check input parameter 

if [ -z "$1" ]; then
	echo "Usage: $0 <mount point>"
	exit 1;
fi

# set envionrment variable to surpress SSL warning from urllib3

export PYTHONWARNINGS=ignore; ./boxfusefs.py $1
