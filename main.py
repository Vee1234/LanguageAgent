from dotenv import load_dotenv
from GeminiClient import GeminiClient

load_dotenv()

def main():
    client = GeminiClient()
    print(client.send_prompt("Give me the most common word in French. Do not return anything other than the word."))

if __name__ == '__main__':
    main()
