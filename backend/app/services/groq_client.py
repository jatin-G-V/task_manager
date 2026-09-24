import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

groq_client = Groq(
    api_key=os.environ.get("GROQ_API_KEY")
)