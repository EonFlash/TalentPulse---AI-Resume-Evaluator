
from .libraries import*
from .workflows import*
from pathlib import Path


# IMPORT YOUR LANGGRAPH / workflow functions here.
# Example placeholder:
# from evaluator.workflows import get_initial_state, workflow_1

def evaluate_resume_file(file_path: str,job_description:str):
    """
    Adapt this to call your LangGraph workflow.
    It must return a JSON-serializable dict.
    """
    try:
        reader = PdfReader(file_path)
        full_text = ""
        for page_num in range(len(reader.pages)):
            page = reader.pages[page_num]
            full_text += page.extract_text()
    except Exception as e:
        print(f"Error reading PDF: {e}")

    result = Evaluate(full_text,job_description)
    # ------------------------------------------------------

    return result
