#!/bin/bash

pip3 install virtualenv
virtualenv venv
source venv/bin/activate

pip3 install -r requirements.txt

python3 bot.py
