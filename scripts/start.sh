#!/bin/bash
source /home/ubuntu/marketbot/sendgrid.env
source /home/ubuntu/marketbot/venv/bin/activate
python /home/ubuntu/marketbot/prod.py 8443 > /home/ubuntu/marketbot.log & 
echo "`ps aux |grep py`" 
