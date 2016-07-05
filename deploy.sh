ssh -i "./botx.pem" ubuntu@ec2-52-34-35-240.us-west-2.compute.amazonaws.com  << EOF
cd ~/marketbot && git pull origin && source venv/bin/activate && pip install -r requirements.txt && echo "`whoami`" &&  (exec "./stop.sh") && (exec "./start.sh") && echo '[OK]'
EOF 