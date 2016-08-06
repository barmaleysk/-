from app import MasterBot

mb = MasterBot({'token': open('token.dev').read()})  # test
mb.start()
