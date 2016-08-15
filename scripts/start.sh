#!/bin/bash
source /home/ubuntu/marketbot/sendgrid.env
source /home/ubuntu/marketbot/venv/bin/activate
python /home/ubuntu/marketbot/webhook_listener.py 8443 &
echo "`ps aux |grep py`" 
