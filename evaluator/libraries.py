from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph,START,END

from typing import Literal,TypedDict,Annotated
from dotenv import load_dotenv
from pydantic import BaseModel,Field

import os,json
load_dotenv()