#!/bin/bash
pkill -f "python prod.py";
pkill -f "/home/ubuntu/marketbot/prod.py";
echo "`ps aux |grep py`" 
