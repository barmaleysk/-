ssh -i "./botx.pem" ubuntu@ec2-52-34-35-240.us-west-2.compute.amazonaws.com << EOF
cd ~/marketbot && git pull origin master && source venv/bin/activate && source sendgrid.env && pip install -r requirements.txt && echo "`whoami`" && sudo /etc/cron.hourly/bot_restart && echo '[OK]'
EOF