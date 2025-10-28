from .libraries import *
from .utils import*
from .llm import*

def Evaluate(full_pdf_data,job_description):

    class ExtractorSchema(BaseModel):
        Name: str=Field(description="Name of the candidate")
        Experience:int= Field(description="The number of years of experience candidate have")
        Match_percentage:int = Field(description="The percentage by which the candidate suits the Job description provided")
        Feedback:str= Field(description="Feedback for matching, and why the candidate got it.") 
    
    class ResumeGrader(BaseModel):
        Resume_grade:Literal['A+','A','A-','B+','B','B-','C+','C','C-','D','f'] = Field(description="")

    class EvaluatorState(TypedDict):
        resume_data:str
        job_description:str
        match_percentage:int
        candidate_name:str
        experience:int
        evaluator_feedback:str
        resume_grade:Literal['A+','A','A-','B+','B','B-','C+','C','C-','D','f']

    structured_llm = llm.with_structured_output(ExtractorSchema)

    def find_match(state:EvaluatorState):
        print("Resume Data Has been extracted!!!")
        prompt = f"For the following data find out the match percentage: {state['resume_data']}, for the following job description: {state['job_description']}, also give valid feedback based on match percentage"
        result = structured_llm.invoke(prompt)
        print("Evaluation complete")

        return {
                "match_percentage": result.Match_percentage,
                "candidate_name": result.Name,
                "experience": result.Experience,
                "feedback":result.Feedback
                }

    graph = StateGraph(EvaluatorState)

    graph.add_node('find_match',find_match)

    graph.add_edge(START,'find_match')
    graph.add_edge('find_match',END)

    workflow=graph.compile()

    initial_state = {
        'resume_data':full_pdf_data,
        'job_description':job_description

    }

    ans=workflow.invoke(initial_state)
    dump_ans_dict_to_json(ans)
    return ans
