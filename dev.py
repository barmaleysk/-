from app import MasterBot

mb = MasterBot({'token': open('token.dev').read().strip()})  # test
mb.start()
