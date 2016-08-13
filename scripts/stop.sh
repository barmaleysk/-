#!/bin/bash
pkill -f "/home/ubuntu/marketbot/bot_worker.py";
pkill -f "/home/ubuntu/marketbot/webhook_listener.py";
echo "`ps aux |grep py`" 
