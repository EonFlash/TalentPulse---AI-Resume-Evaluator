from evaluator.libraries import *

llm = ChatGoogleGenerativeAI(
    model= "gemini-2.5-pro",
    temperature=1.0,
    max_retries=2,
    google_api_key=os.getenv('GEMINI_API_KEY'),
)

