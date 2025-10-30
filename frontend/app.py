import streamlit as st
import requests

st.title("KPI Factory Dashboard")

# KPI Management
st.header("KPIs")
kpi_name = st.text_input("KPI Name")
kpi_description = st.text_area("KPI Description")
kpi_formula = st.text_input("KPI Formula")

if st.button("Create KPI"):
    kpi_id = "kpi_" + kpi_name.lower().replace(" ", "_")
    response = requests.post("http://127.0.0.1:8000/kpis/", json={
        "id": kpi_id,
        "name": kpi_name,
        "description": kpi_description,
        "formula": kpi_formula
    })
    if response.status_code == 200:
        st.success("KPI created successfully!")
    else:
        st.error("Failed to create KPI.")

st.subheader("Existing KPIs")
response = requests.get("http://127.0.0.1:8000/kpis/")
if response.status_code == 200:
    st.json(response.json())

# Prompt Management
st.header("Prompts")
prompt_text = st.text_area("Prompt Text")

if st.button("Create Prompt"):
    prompt_id = "prompt_" + str(hash(prompt_text))
    response = requests.post("http://127.0.0.1:8000/prompts/", json={
        "id": prompt_id,
        "text": prompt_text
    })
    if response.status_code == 200:
        st.success("Prompt created successfully!")
    else:
        st.error("Failed to create prompt.")

st.subheader("Existing Prompts")
response = requests.get("http://127.0.0.1:8000/prompts/")
if response.status_code == 200:
    st.json(response.json())

# Appraisal
st.header("Appraisal")
prompt_to_appraise = st.selectbox("Select Prompt to Appraise", [p["id"] for p in requests.get("http://127.0.0.1:8000/prompts/").json()])
if st.button("Appraise Prompt"):
    # This is a placeholder for the actual appraisal logic
    scores = {"kpi_1": 0.8, "kpi_2": 0.5}
    response = requests.post("http://127.0.0.1:8000/appraisals/", json={
        "prompt_id": prompt_to_appraise,
        "scores": scores
    })
    if response.status_code == 200:
        st.success("Appraisal successful!")
        st.json(response.json())
    else:
        st.error("Appraisal failed.")
