from gevent import monkey
monkey.patch_all()

from app import MasterBot

if __name__ == "__main__":
    MasterBot({'token': open('token').read().replace('\n', '')}).run()  # some strange bug
