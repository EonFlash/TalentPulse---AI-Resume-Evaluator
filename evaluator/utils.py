from .libraries import*

def get_test_resume(path:str)->str:

    with open(path,'r') as file:
        resume_data=file.read()
    
    return resume_data

def get_job_description(path:str)->str:
    with open(path,'r') as file:
        job_description=file.read()
    
    return job_description

def get_initial_state()->dict:
    test_data=get_test_resume("test_resume.txt")
    job_desc= get_job_description("jd.txt")
    initial_state = {
        'resume_data':test_data,
        'job_description':job_desc
    }

    return initial_state


def dump_ans_dict_to_json(ans:dict)->None:

    with open('results.json','w') as out_file:
        json.dump(ans,out_file)