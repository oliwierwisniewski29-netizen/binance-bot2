#!/bin/bash
source venv/bin/activate
nohup python3 bbod.py > bot.log 2>&1 &
