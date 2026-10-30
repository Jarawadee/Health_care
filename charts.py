import pandas as pd
import plotly.express as px

def records_frame(records):
    rows=[]
    for d in records:
        v=d.get("vertigo") or {}; h=d.get("headache") or {}; s=d.get("sleep") or {}; l=d.get("lifestyle") or {}
        severities=[x for x in (v.get("severity") if v.get("has_symptom") else None,
                                h.get("severity") if h.get("has_symptom") else None) if x is not None]
        rows.append({
            "date":pd.to_datetime(d["entry_date"]),
            "เวียนศีรษะ":v.get("severity") if v.get("has_symptom") else None,
            "ปวดศีรษะ":h.get("severity") if h.get("has_symptom") else None,
            "ระดับอาการเฉลี่ย":sum(severities)/len(severities) if severities else None,
            "ชั่วโมงนอน":s.get("duration_hours"), "ความเครียด":l.get("stress"),
            "ความเหนื่อยล้า":l.get("fatigue"),
            "มีอาการ":bool((v.get("has_symptom") or h.get("has_symptom")))
        })
    return pd.DataFrame(rows)

def symptom_chart(df):
    data=df.melt(id_vars="date",value_vars=["เวียนศีรษะ","ปวดศีรษะ"],var_name="ประเภท",value_name="ระดับ (0–10)").dropna()
    if data.empty: return None
    return px.line(data,x="date",y="ระดับ (0–10)",color="ประเภท",markers=True,
                   title="แนวโน้มระดับอาการ",range_y=[0,10])

def sleep_chart(df):
    data=df.dropna(subset=["ชั่วโมงนอน"])
    if data.empty: return None
    return px.bar(data,x="date",y="ชั่วโมงนอน",title="ระยะเวลานอน",labels={"ชั่วโมงนอน":"ชั่วโมง"})

def correlation_chart(df, factor):
    data=df.dropna(subset=[factor,"ระดับอาการเฉลี่ย"])
    if len(data)<3: return None
    return px.scatter(data,x=factor,y="ระดับอาการเฉลี่ย",trendline="ols",
                      title=f"ข้อมูลที่บันทึก: {factor} กับระดับอาการเฉลี่ย")
