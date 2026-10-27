import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

def symptom_trend(symptoms):
    if symptoms.empty: return None
    data = symptoms.copy()
    data["record_date"] = pd.to_datetime(data["record_date"], errors="coerce")
    cols = [c for c in ["dizziness", "headache", "nausea"] if c in data]
    if not cols: return None
    daily = data.groupby("record_date")[cols].max().reset_index().melt(
        id_vars="record_date", var_name="อาการ", value_name="คะแนนสูงสุด")
    names = {"dizziness":"เวียนศีรษะ", "headache":"ปวดศีรษะ", "nausea":"คลื่นไส้"}
    daily["อาการ"] = daily["อาการ"].map(names).fillna(daily["อาการ"])
    if daily["คะแนนสูงสุด"].notna().sum() == 0: return None
    fig = px.line(daily, x="record_date", y="คะแนนสูงสุด", color="อาการ", markers=True,
                  range_y=[0,10], labels={"record_date":"วันที่","คะแนนสูงสุด":"คะแนน (0–10)"})
    fig.update_layout(legend_title_text="อาการ")
    return fig

def symptom_frequency(symptoms):
    if symptoms.empty: return None
    counts = symptoms["main_symptom"].fillna("ไม่ระบุ").value_counts().rename_axis("อาการ").reset_index(name="จำนวนครั้ง")
    return px.bar(counts, x="อาการ", y="จำนวนครั้ง", color="อาการ", labels={"จำนวนครั้ง":"จำนวน episode"})

def sleep_scatter(daily, symptoms):
    if daily.empty or symptoms.empty: return None
    d = daily[["record_date","sleep_hours","sleep_quality"]].copy()
    s = symptoms[["record_date","dizziness","main_symptom"]].copy()
    d["record_date"] = d["record_date"].astype(str); s["record_date"] = s["record_date"].astype(str)
    s = s.groupby("record_date", as_index=False).agg(dizziness=("dizziness","max"), symptom=("main_symptom","first"))
    merged = d.merge(s, on="record_date").dropna(subset=["sleep_hours","dizziness"])
    if merged.empty: return None
    fig = px.scatter(merged, x="sleep_hours", y="dizziness", color="sleep_quality",
                     hover_data=["record_date","symptom"], range_y=[0,10],
                     labels={"sleep_hours":"ระยะเวลานอน (ชั่วโมง)","dizziness":"คะแนนเวียนศีรษะ","sleep_quality":"คุณภาพการนอน"})
    return fig

def medication_timeline(meds, symptoms):
    fig = go.Figure()
    if not meds.empty:
        m = meds.copy()
        m["เวลา"] = m["record_date"].astype(str) + " " + m["taken_time"].fillna("")
        fig.add_trace(go.Scatter(x=m["เวลา"], y=["ยา: "+str(x) for x in m["name"]],
            mode="markers", name="ยา", text=m["dose"].fillna(""), hovertemplate="%{y}<br>%{x}<br>%{text}<extra></extra>"))
    if not symptoms.empty:
        s = symptoms.copy()
        s["เวลา"] = s["record_date"].astype(str) + " " + s["onset_time"].fillna("")
        fig.add_trace(go.Scatter(x=s["เวลา"], y=["อาการ: "+str(x) for x in s["main_symptom"]],
            mode="markers", name="อาการ", text=s["severity"].fillna(""), hovertemplate="%{y}<br>%{x}<br>คะแนน: %{text}<extra></extra>"))
    if not fig.data: return None
    fig.update_layout(xaxis_title="วันที่และเวลา", yaxis_title="รายการ", height=420)
    return fig
