from app import MasterBot

if __name__ == "__main__":
    # MasterBot({'token': '203526047:AAEmQJLm1JXmBgPeEQCZqkktReRUlup2Fgw'}).start()
    MasterBot({'token': open('token.dev').read()}).start()
    while True:
        pass
