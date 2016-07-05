ssh -i "./botx.pem" ubuntu@ec2-52-34-35-240.us-west-2.compute.amazonaws.com << EOF
cd ~/botx && git pull origin && ~/botx/stop.sh && ~/botx/start.sh
EOF