ssh -i "./botx.pem" ubuntu@ec2-52-34-35-240.us-west-2.compute.amazonaws.com << EOF
cd ~/marketbot && git pull origin && ~/marketbot/stop.sh && ~/marketbot/start.sh
EOF