from dotenv import load_dotenv
from GeminiClient import GeminiClient

load_dotenv()

def main():
    client = GeminiClient("French")
    print(client.send_prompt("Give me the most common word in this language"))

if __name__ == '__main__':
    main()
