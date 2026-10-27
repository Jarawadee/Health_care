from datetime import date, datetime, time, timedelta
from io import BytesIO
import json
import pandas as pd
import streamlit as st
from database import init_db, fetch_records, insert_record, upsert_daily, update_record, delete_record, export_all, import_csv
from utils import sleep_duration_hours, validate_score, time_of_day
from charts import symptom_trend, symptom_frequency, sleep_scatter, medication_timeline

st.set_page_config(page_title="Health Diary", page_icon="💙", layout="wide")
init_db()
st.markdown("""
<style>
.stApp {background:#f4f8fc;color:#18324b}
section[data-testid="stSidebar"] {background:#e8f2fb}
div[data-testid="stMetric"] {background:white;border:1px solid #dbe8f4;padding:16px;border-radius:16px;box-shadow:0 3px 12px #16324f0b}
div.stButton>button, div.stDownloadButton>button {border-radius:10px}
h1,h2,h3 {color:#214d76}
</style>
""", unsafe_allow_html=True)

st.sidebar.title("💙 Health Diary")
st.sidebar.caption("บันทึกสุขภาพรายวัน")
page = st.sidebar.radio("เมนู", ["ภาพรวม","บันทึกประจำวัน","วิเคราะห์อาการ","การนอนและไลฟ์สไตล์","ประวัติยา","จัดการประวัติ","ส่งออกและตั้งค่า"])
today = date.today()
with st.sidebar:
    st.markdown("---")
    start = st.date_input("ตั้งแต่วันที่", value=today-timedelta(days=30), key="filter_start")
    end = st.date_input("ถึงวันที่", value=today, key="filter_end")
    if start > end:
        st.error("วันที่เริ่มต้นต้องไม่เกินวันที่สิ้นสุด")
        start, end = end, start
    if st.button("ล้างตัวกรอง"):
        st.session_state["filter_start"] = today-timedelta(days=30)
        st.session_state["filter_end"] = today
        st.rerun()

daily = fetch_records("daily", start, end)
meals = fetch_records("meals", start, end)
symptoms = fetch_records("symptoms", start, end)
meds = fetch_records("medications", start, end)
st.sidebar.caption(f"ช่วงข้อมูล: {start:%d/%m/%Y} – {end:%d/%m/%Y}")

def score_input(label, key, default=0.0):
    return st.slider(label, 0.0, 10.0, float(default), 0.5, key=key)

def as_text(value):
    return "" if value is None else str(value)

if page == "ภาพรวม":
    st.title("Health Diary — Personal Wellness Dashboard")
    st.caption("บันทึกสุขภาพรายวัน เพื่อสังเกตแนวโน้มของอาการ การนอน อาหาร และการใช้ยา")
    st.info("แอปนี้ใช้บันทึกข้อมูลและสังเกตแนวโน้ม ไม่สามารถวินิจฉัยโรคหรือระบุสาเหตุของอาการได้")
    recorded_days = daily["record_date"].nunique() if not daily.empty else 0
    symptomatic_days = symptoms.loc[symptoms["main_symptom"] != "ไม่มีอาการ", "record_date"].nunique() if not symptoms.empty else 0
    avg_sleep = daily["sleep_hours"].dropna().mean() if not daily.empty and daily["sleep_hours"].notna().any() else None
    avg_dizzy = symptoms["dizziness"].dropna().mean() if not symptoms.empty and symptoms["dizziness"].notna().any() else None
    avg_head = symptoms["headache"].dropna().mean() if not symptoms.empty and symptoms["headache"].notna().any() else None
    metrics = [
        ("วันที่บันทึก", str(recorded_days)),
        ("วันที่มีอาการ", str(symptomatic_days)),
        ("นอนเฉลี่ย", f"{avg_sleep:.1f} ชม." if avg_sleep is not None else "—"),
        ("เวียนศีรษะเฉลี่ย", f"{avg_dizzy:.1f}/10" if avg_dizzy is not None else "—"),
        ("ปวดศีรษะเฉลี่ย", f"{avg_head:.1f}/10" if avg_head is not None else "—"),
        ("จำนวน episode", str(len(symptoms)) if not symptoms.empty else "0"),
    ]
    cols = st.columns(6)
    for col,(label,value) in zip(cols,metrics): col.metric(label,value)
    st.subheader("แนวโน้มความรุนแรงของอาการ")
    fig = symptom_trend(symptoms)
    if fig: st.plotly_chart(fig, use_container_width=True)
    else: st.info("ยังไม่มีข้อมูลคะแนนอาการที่เพียงพอสำหรับกราฟ")
    left,right = st.columns(2)
    with left:
        st.subheader("ความถี่อาการ")
        fig = symptom_frequency(symptoms)
        if fig: st.plotly_chart(fig,use_container_width=True)
        else: st.info("ยังไม่มีรายการอาการ")
    with right:
        st.subheader("ระยะเวลานอนเทียบกับเวียนศีรษะ")
        fig = sleep_scatter(daily,symptoms)
        if fig: st.plotly_chart(fig,use_container_width=True)
        else: st.info("ต้องมีข้อมูลการนอนและคะแนนเวียนศีรษะที่บันทึกไว้ก่อน")
    st.caption("กราฟรายวันใช้คะแนนสูงสุดของแต่ละอาการในวันนั้น จำนวน episode คือจำนวนรายการที่บันทึก ไม่ใช่จำนวนวันที่มีอาการ")
    st.subheader("รายการล่าสุด")
    if not symptoms.empty: st.dataframe(symptoms.head(10), use_container_width=True, hide_index=True)
    else: st.write("เริ่มบันทึกข้อมูลเพื่อดูแนวโน้มของคุณ")
    st.warning("หากเวียนศีรษะร่วมกับปวดศีรษะรุนแรงฉับพลัน พูดลำบาก อ่อนแรง/ชาหรือเกิดอาการใหม่ เห็นภาพซ้อน หรือเดินไม่ได้ ควรรับการประเมินทางการแพทย์ฉุกเฉิน")

elif page == "บันทึกประจำวัน":
    st.title("บันทึกสุขภาพ")
    st.caption("ช่องที่ไม่ทราบสามารถเว้นว่างได้ และสามารถบันทึกหลายมื้อหรือหลาย episode ในวันเดียวกัน")
    entry_date = st.date_input("วันที่บันทึก", value=today)
    st.subheader("การนอนและไลฟ์สไตล์")
    existing = fetch_records("daily", entry_date, entry_date)
    old = existing.iloc[0].to_dict() if not existing.empty else {}
    with st.form("daily_form"):
        c1,c2,c3 = st.columns(3)
        bed = c1.time_input("เวลาเข้านอน", value=time.fromisoformat(old["bedtime"]) if old.get("bedtime") else time(23,0))
        wake = c2.time_input("เวลาตื่น", value=time.fromisoformat(old["wake_time"]) if old.get("wake_time") else time(7,0))
        quality = c3.slider("คุณภาพการนอน (0–10)",0.0,10.0,float(old.get("sleep_quality") or 5.0),0.5)
        c4,c5,c6 = st.columns(3)
        water = c4.number_input("น้ำดื่มรวม (มล.)",min_value=0.0,value=float(old.get("water_ml") or 0),step=250.0)
        stress = c5.slider("ความเครียด (0–10)",0.0,10.0,float(old.get("stress_level") or 0),0.5)
        activity = c6.text_input("กิจกรรมทางกาย",value=as_text(old.get("physical_activity")))
        sleep_notes = st.text_area("บันทึกการนอน",value=as_text(old.get("sleep_notes")))
        cycle = st.text_input("ข้อมูลรอบเดือน (ไม่บังคับ)",value=as_text(old.get("menstrual_cycle")))
        lifestyle = st.text_area("บันทึกไลฟ์สไตล์อื่น ๆ",value=as_text(old.get("lifestyle_notes")))
        save_daily = st.form_submit_button("บันทึกข้อมูลประจำวัน")
    if save_daily:
        hours = sleep_duration_hours(bed,wake)
        upsert_daily({"record_date":str(entry_date),"bedtime":bed.strftime("%H:%M"),"wake_time":wake.strftime("%H:%M"),
                      "sleep_hours":hours,"sleep_quality":quality,"sleep_notes":sleep_notes or None,"water_ml":water,
                      "physical_activity":activity or None,"stress_level":stress,"menstrual_cycle":cycle or None,
                      "lifestyle_notes":lifestyle or None})
        st.success("บันทึกข้อมูลประจำวันแล้ว")
    st.divider()
    st.subheader("เพิ่มมื้ออาหารหรือเครื่องดื่ม")
    with st.form("meal_form", clear_on_submit=True):
        c1,c2,c3 = st.columns(3)
        meal_time = c1.time_input("เวลาที่รับประทาน",value=time(12,0),key="meal_time")
        category = c2.selectbox("ประเภท",["อาหารเช้า","อาหารกลางวัน","อาหารเย็น","ของว่าง","เครื่องดื่ม","อื่น ๆ"])
        name = c3.text_input("ชื่ออาหาร/เครื่องดื่ม *")
        c4,c5,c6 = st.columns(3)
        amount = c4.text_input("ปริมาณโดยประมาณ")
        caffeine = c5.selectbox("คาเฟอีน",["ไม่ทราบ","มี","ไม่มี"])
        meal_water = c6.number_input("น้ำจากรายการนี้ (มล.)",min_value=0.0,value=0.0,step=100.0)
        notes = st.text_input("หมายเหตุ")
        add_meal = st.form_submit_button("เพิ่มรายการอาหาร/เครื่องดื่ม")
    if add_meal:
        if not name.strip(): st.error("กรุณาระบุชื่ออาหารหรือเครื่องดื่ม")
        else:
            insert_record("meals",{"record_date":str(entry_date),"consumed_time":meal_time.strftime("%H:%M"),"category":category,
                "name":name.strip(),"amount":amount or None,"caffeine":caffeine,"water_ml":meal_water,"notes":notes or None})
            st.success("เพิ่มรายการแล้ว")
    st.divider()
    st.subheader("เพิ่ม episode อาการ")
    with st.form("symptom_form", clear_on_submit=True):
        c1,c2,c3 = st.columns(3)
        onset = c1.time_input("เวลาเริ่มอาการ",value=time(12,0),key="sym_onset")
        end_time = c2.time_input("เวลาที่ดีขึ้น/สิ้นสุด (ไม่บังคับ)",value=time(12,0),key="sym_end")
        symptom = c3.selectbox("อาการหลัก",["เวียนศีรษะ / บ้านหมุน","ปวดศีรษะ","คลื่นไส้","อ่อนเพลีย","อื่น ๆ","ไม่มีอาการ"])
        c4,c5,c6 = st.columns(3)
        severity = c4.slider("ความรุนแรงโดยรวม",0.0,10.0,0.0,0.5,key="sev")
        dizzy = c5.slider("เวียนศีรษะ (0–10)",0.0,10.0,0.0,0.5,key="dizzy")
        headache = c6.slider("ปวดศีรษะ (0–10)",0.0,10.0,0.0,0.5,key="headache")
        nausea = st.slider("คลื่นไส้ (0–10)",0.0,10.0,0.0,0.5,key="nausea")
        associated = st.text_input("อาการร่วม")
        triggers = st.text_input("สิ่งที่อาจกระตุ้น/กิจกรรมก่อนเกิดอาการ")
        interfered = st.selectbox("กระทบกิจวัตรหรือไม่",["ไม่ทราบ","ไม่","ใช่"])
        helped = st.text_input("สิ่งที่ช่วยให้อาการดีขึ้น")
        symptom_notes = st.text_area("หมายเหตุอาการ")
        add_symptom = st.form_submit_button("บันทึก episode อาการ")
    if add_symptom:
        insert_record("symptoms",{"record_date":str(entry_date),"onset_time":onset.strftime("%H:%M"),
            "end_time":end_time.strftime("%H:%M") if end_time != time(12,0) else None,"main_symptom":symptom,
            "severity":severity,"dizziness":dizzy,"headache":headache,"nausea":nausea,"associated":associated or None,
            "potential_triggers":triggers or None,"interfered":interfered,"helped":helped or None,"notes":symptom_notes or None})
        st.success("บันทึก episode อาการแล้ว")
    st.divider()
    st.subheader("เพิ่มรายการยา")
    with st.form("med_form",clear_on_submit=True):
        c1,c2,c3 = st.columns(3)
        med_name = c1.text_input("ชื่อยา *")
        dose = c2.text_input("ขนาดยาและหน่วย")
        taken = c3.time_input("เวลาที่รับประทาน",value=time(12,0),key="med_time")
        reason = st.text_input("เหตุผลที่ใช้ยา")
        followed = st.selectbox("ใช้ตามฉลาก/คำสั่งเดิมหรือไม่",["ไม่ทราบ","ใช่","ไม่ใช่"])
        effect = st.text_input("ผลที่สังเกตได้")
        side = st.text_input("ผลข้างเคียงที่สังเกตได้")
        med_notes = st.text_area("หมายเหตุยา")
        add_med = st.form_submit_button("บันทึกรายการยา")
    if add_med:
        if not med_name.strip(): st.error("กรุณาระบุชื่อยา")
        else:
            insert_record("medications",{"record_date":str(entry_date),"name":med_name.strip(),"dose":dose or None,
                "taken_time":taken.strftime("%H:%M"),"reason":reason or None,"followed_instructions":followed,
                "reported_effect":effect or None,"side_effects":side or None,"notes":med_notes or None})
            st.success("บันทึกรายการยาแล้ว")
    st.caption("ข้อมูลยาเป็นเพียงบันทึกส่วนตัว ไม่ใช้แทนฉลากยา/คำแนะนำจากบุคลากรทางการแพทย์")

elif page == "วิเคราะห์อาการ":
    st.title("วิเคราะห์อาการ")
    if symptoms.empty: st.info("ยังไม่มีข้อมูลอาการในช่วงวันที่เลือก")
    else:
        options = ["ทั้งหมด"] + sorted(symptoms["main_symptom"].dropna().unique().tolist())
        selected = st.selectbox("กรองตามอาการ",options)
        view = symptoms if selected=="ทั้งหมด" else symptoms[symptoms["main_symptom"]==selected]
        c1,c2,c3 = st.columns(3)
        c1.metric("จำนวน episode",len(view))
        vals = view["severity"].dropna()
        c2.metric("คะแนนเฉลี่ย",f"{vals.mean():.1f}/10" if len(vals) else "—")
        c3.metric("คะแนนสูงสุด",f"{vals.max():.1f}/10" if len(vals) else "—")
        view = view.copy()
        view["ช่วงเวลา"] = view["onset_time"].apply(time_of_day)
        st.bar_chart(view["ช่วงเวลา"].value_counts())
        st.dataframe(view, use_container_width=True, hide_index=True)
        st.caption("เวลาเริ่มและสิ้นสุดที่ไม่ทราบจะไม่ถูกเติมให้เอง ระยะเวลาที่ข้ามเที่ยงคืนต้องตีความร่วมกับวันที่จริง")

elif page == "การนอนและไลฟ์สไตล์":
    st.title("การนอนและไลฟ์สไตล์")
    if daily.empty: st.info("ยังไม่มีข้อมูลการนอนในช่วงวันที่เลือก")
    else:
        daily = daily.copy()
        daily["record_date"] = pd.to_datetime(daily["record_date"],errors="coerce")
        st.metric("ระยะเวลานอนเฉลี่ย",f"{daily['sleep_hours'].mean():.1f} ชั่วโมง" if daily["sleep_hours"].notna().any() else "—")
        st.line_chart(daily.set_index("record_date")[["sleep_hours","sleep_quality"]])
        st.subheader("น้ำดื่มและความเครียด")
        st.dataframe(daily[["record_date","water_ml","stress_level","physical_activity","lifestyle_notes"]],use_container_width=True,hide_index=True)
        if not meals.empty:
            st.subheader("อาหารและคาเฟอีนที่บันทึก")
            st.dataframe(meals[["record_date","consumed_time","category","name","caffeine","water_ml"]],use_container_width=True,hide_index=True)
        st.caption("ความสัมพันธ์ที่เห็นเป็นเพียงรูปแบบร่วมในข้อมูล ไม่ได้ยืนยันว่าเป็นสาเหตุ")

elif page == "ประวัติยา":
    st.title("ประวัติยา")
    if meds.empty: st.info("ยังไม่มีข้อมูลยาในช่วงวันที่เลือก")
    else:
        names = ["ทั้งหมด"] + sorted(meds["name"].dropna().unique().tolist())
        choice = st.selectbox("กรองตามชื่อยา",names)
        view = meds if choice=="ทั้งหมด" else meds[meds["name"]==choice]
        st.dataframe(view, use_container_width=True, hide_index=True)
    st.subheader("ไทม์ไลน์ยาและอาการ")
    fig = medication_timeline(meds,symptoms)
    if fig: st.plotly_chart(fig,use_container_width=True)
    else: st.info("ยังไม่มีข้อมูลเพียงพอสำหรับไทม์ไลน์")
    st.caption("อย่าใช้กราฟนี้เพื่อสรุปว่ายาทำให้อาการดีขึ้นหรือแย่ลง")

elif page == "จัดการประวัติ":
    st.title("ค้นหา แก้ไข และลบรายการ")
    table_labels = {"อาหาร/เครื่องดื่ม":"meals","อาการ":"symptoms","ยา":"medications"}
    label = st.selectbox("ประเภทข้อมูล",list(table_labels))
    table = table_labels[label]
    frame = fetch_records(table,start,end)
    query = st.text_input("ค้นหาข้อความ")
    if query:
        mask = frame.astype(str).apply(lambda col: col.str.contains(query,case=False,na=False)).any(axis=1)
        frame = frame[mask]
    st.dataframe(frame,use_container_width=True,hide_index=True)
    if not frame.empty:
        ids = frame["id"].astype(int).tolist()
        record_id = st.selectbox("เลือก ID ที่ต้องการแก้ไข/ลบ",ids)
        row = frame[frame["id"]==record_id].iloc[0].to_dict()
        with st.expander("แก้ไขรายการที่เลือก"):
            editable = {}
            excluded = {"id","created_at","updated_at"}
            with st.form("edit_form"):
                for col,val in row.items():
                    if col in excluded: continue
                    editable[col] = st.text_input(col, value="" if pd.isna(val) else str(val), key=f"edit_{col}")
                save_edit = st.form_submit_button("บันทึกการแก้ไข")
            if save_edit:
                update_record(table,record_id,editable)
                st.success("แก้ไขแล้ว"); st.rerun()
        with st.expander("ลบรายการที่เลือก"):
            st.warning("การลบไม่สามารถย้อนกลับได้")
            confirm = st.checkbox(f"ยืนยันลบ ID {record_id}",key=f"confirm_{table}_{record_id}")
            if st.button("ลบรายการ",disabled=not confirm):
                delete_record(table,record_id)
                st.success("ลบแล้ว"); st.rerun()

elif page == "ส่งออกและตั้งค่า":
    st.title("ส่งออกข้อมูลและตั้งค่า")
    st.write("ข้อมูลจัดเก็บในไฟล์ SQLite ภายในโฟลเดอร์ `data/health_diary.sqlite3` บนเครื่องที่รันแอป")
    st.subheader("ส่งออก")
    all_tables = export_all()
    for table,frame in all_tables.items():
        st.download_button(f"ดาวน์โหลด {table}.csv",frame.to_csv(index=False).encode("utf-8-sig"),file_name=f"{table}.csv",mime="text/csv")
    if st.button("สร้างไฟล์ Excel รวมทุกตาราง"):
        buffer = BytesIO()
        with pd.ExcelWriter(buffer,engine="openpyxl") as writer:
            for table,frame in all_tables.items(): frame.to_excel(writer,sheet_name=table,index=False)
        st.download_button("ดาวน์โหลด health_diary.xlsx",buffer.getvalue(),file_name="health_diary.xlsx",mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    st.subheader("นำเข้า CSV")
    import_table = st.selectbox("ตารางปลายทาง",["daily","meals","symptoms","medications"])
    upload = st.file_uploader("เลือกไฟล์ CSV",type=["csv"])
    if upload:
        st.caption("ตรวจสอบไฟล์ก่อนนำเข้า รายการซ้ำอาจถูกปฏิเสธด้วยข้อจำกัดฐานข้อมูล")
        if st.button("นำเข้าข้อมูลจาก CSV"):
            try:
                imported,rejected = import_csv(import_table,upload)
                st.success(f"นำเข้าสำเร็จ {imported} แถว")
                if rejected: st.warning(f"ไม่ได้นำเข้า {len(rejected)} แถว"); st.dataframe(pd.DataFrame(rejected))
            except Exception as exc: st.error(f"ไม่สามารถนำเข้าไฟล์ได้: {exc}")
    st.subheader("ความเป็นส่วนตัวและการสำรองข้อมูล")
    st.write("แอปนี้ไม่ส่งข้อมูลไปยัง API ภายนอกโดยเจตนา แต่ความปลอดภัยขึ้นกับเครื่อง ระบบปฏิบัติการ และการเข้าถึงไฟล์ด้วย")
    st.write("สำรองข้อมูลโดยหยุดแอป แล้วคัดลอก `data/health_diary.sqlite3` ไปเก็บในที่ปลอดภัย")
    st.write("หากเปิดใช้ผ่านอินเทอร์เน็ต ต้องตั้งค่าการยืนยันตัวตน การควบคุมสิทธิ์ HTTPS และพื้นที่จัดเก็บที่ได้รับการปกป้องก่อนใช้ข้อมูลสุขภาพจริง")
