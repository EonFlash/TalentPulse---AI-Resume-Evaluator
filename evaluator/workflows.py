from .libraries import *
from .utils import*
from .llm import*

def workflow_1 (initial_state_1):

    class ExtractorSchema(BaseModel):
        Name: str=Field(description="Name of the candidate")
        Experience:int= Field(description="The number of years of experience candidate have")
        Match_percentage:int = Field(description="The percentage by which the candidate suits the Job description provided") 

    class EvaluatorState(TypedDict):
        resume_data:str
        job_description:str
        match_percentage:int
        candidate_name:str
        experience:int

    structured_llm = llm.with_structured_output(ExtractorSchema)

    def find_match(state:EvaluatorState):
        print("Resume Data Has been extracted!!!")
        prompt = f"For the following data find out the match percentage: {state['resume_data']}, for the following job description: {state['job_description']}"
        result = structured_llm.invoke(prompt)
        print("Evaluation complete")

        return {
                "match_percentage": result.Match_percentage,
                "candidate_name": result.Name,
                "experience": result.Experience
                }

    graph = StateGraph(EvaluatorState)

    graph.add_node('find_match',find_match)

    graph.add_edge(START,'find_match')
    graph.add_edge('find_match',END)

    workflow=graph.compile()

    initial_state = initial_state_1

    ans=workflow.invoke(initial_state)

    dump_ans_dict_to_json(ans)
