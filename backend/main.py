from fastapi import FastAPI
from .models import KPI, Prompt, Appraisal
from typing import List, Dict

app = FastAPI()

kpis: Dict[str, KPI] = {}
prompts: Dict[str, Prompt] = {}
appraisals: Dict[str, Appraisal] = {}

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.post("/kpis/", response_model=KPI)
def create_kpi(kpi: KPI):
    kpis[kpi.id] = kpi
    return kpi

@app.get("/kpis/", response_model=List[KPI])
def list_kpis():
    return list(kpis.values())

@app.post("/prompts/", response_model=Prompt)
def create_prompt(prompt: Prompt):
    prompts[prompt.id] = prompt
    return prompt

@app.get("/prompts/", response_model=List[Prompt])
def list_prompts():
    return list(prompts.values())

@app.post("/appraisals/", response_model=Appraisal)
def create_appraisal(appraisal: Appraisal):
    appraisals[appraisal.prompt_id] = appraisal
    return appraisal

@app.get("/appraisals/{prompt_id}", response_model=Appraisal)
def get_appraisal(prompt_id: str):
    return appraisals.get(prompt_id)
