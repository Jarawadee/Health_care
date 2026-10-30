from datetime import date, time, timedelta
import json
import streamlit as st
import pandas as pd
import database as db
from utils import sleep_duration, validate_severity
from charts import records_frame, symptom_chart, sleep_chart, correlation_chart

st.set_page_config(page_title="Health Diary", page_icon="🌿", layout="wide")
db.init_db()

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Sarabun:wght@400;500;600;700&display=swap');
html, body, [class*="css"] {font-family:'Sarabun','Noto Sans Thai',Tahoma,sans-serif;}
.stApp {background:#F8F7FB;color:#343447;}
.block-container {max-width:1180px;padding-top:2rem;padding-bottom:3rem;}
h1,h2,h3 {color:#343447;letter-spacing:-.3px;}
div[data-testid="stMetric"] {background:#fff;border:1px solid #eeeaf4;padding:18px;border-radius:18px;box-shadow:0 3px 14px #3434470a;}
div[data-testid="stForm"] {background:#fff;border:1px solid #eeeaf4;padding:18px;border-radius:18px;}
.stButton>button,.stDownloadButton>button {border-radius:12px;border:0;background:#DCEAF7;color:#343447;font-weight:600;min-height:42px;}
.stButton>button:hover {background:#C8DDF0;color:#343447;border:0;}
div[data-testid="stExpander"] {background:#fff;border:1px solid #eeeaf4;border-radius:14px;}
div[data-testid="stAlert"] {border-radius:14px;}
.small-muted {color:#77778A;font-size:.92rem;}
.hero {background:linear-gradient(110deg,#FFF9F0,#F6E1E5 55%,#E8E1F5);padding:26px 30px;border-radius:22px;margin-bottom:18px;}
.hero p {color:#77778A;margin-bottom:0;}
section[data-testid="stSidebar"] {background:#FFF9F0;}
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("## 🌿 Health Diary")
    st.caption("My Personal Wellness Journal")
    page=st.radio("เมนูหลัก",["ภาพรวมสุขภาพ","บันทึกประจำวัน","ปฏิทินและประวัติ","วิเคราะห์อาการ","ส่งออก / นำเข้าข้อมูล","ความเป็นส่วนตัว"])
    st.divider()
    st.caption("ข้อมูลจัดเก็บในเครื่องนี้ที่ data/health_diary.db")

def date_range():
    choice=st.selectbox("ช่วงเวลาที่ต้องการดู",["7 วันล่าสุด","30 วันล่าสุด","90 วันล่าสุด","กำหนดช่วงวันที่"])
    today=date.today()
    if choice=="กำหนดช่วงวันที่":
        c1,c2=st.columns(2)
        start=c1.date_input("ตั้งแต่",today-timedelta(days=29))
        end=c2.date_input("ถึง",today)
    else:
        n={"7 วันล่าสุด":7,"30 วันล่าสุด":30,"90 วันล่าสุด":90}[choice]
        start,end=today-timedelta(days=n-1),today
    if start>end: st.warning("วันที่เริ่มต้นต้องไม่อยู่หลังวันที่สิ้นสุด"); return None,None
    return start,end

def severity_input(label,key):
    enabled=st.checkbox(f"มีอาการ{label}",key=key+"_yes")
    return enabled, (st.slider(f"ระดับความรุนแรง{label} (0–10)",0,10,5,key=key+"_severity") if enabled else None)

def show_day(d):
    st.subheader(d["entry_date"])
    st.write(d.get("daily_note") or "ไม่มีหมายเหตุประจำวัน")
    a,b=st.columns(2)
    with a:
        st.markdown("**การนอน**")
        st.write(d["sleep"] or "ไม่มีข้อมูล")
        st.markdown("**เวียนศีรษะ**"); st.write(d["vertigo"] or "ไม่มีข้อมูล")
        st.markdown("**ปวดศีรษะ**"); st.write(d["headache"] or "ไม่มีข้อมูล")
    with b:
        st.markdown("**อาหารและเครื่องดื่ม**"); st.dataframe(pd.DataFrame(d["meals"]) if d["meals"] else pd.DataFrame(),use_container_width=True)
        st.markdown("**ยา**"); st.dataframe(pd.DataFrame(d["medications"]) if d["medications"] else pd.DataFrame(),use_container_width=True)
        st.markdown("**ไลฟ์สไตล์**"); st.write(d["lifestyle"] or "ไม่มีข้อมูล")

if page=="ภาพรวมสุขภาพ":
    st.markdown(f'<div class="hero"><h1>ยินดีต้อนรับกลับมา 🌿</h1><p>วันนี้เป็นอย่างไรบ้าง? ค่อย ๆ บันทึกเท่าที่คุณสะดวก ไม่จำเป็นต้องกรอกทุกช่อง</p><p>{date.today().strftime("%d %B %Y")}</p></div>',unsafe_allow_html=True)
    start,end=date_range()
    if start and end:
        records=db.list_history(start,end)
        df=records_frame(records)
        days=len(records); vertigo=sum(bool(x["vertigo"].get("has_symptom")) for x in records)
        sleep=df["ชั่วโมงนอน"].dropna().mean() if not df.empty else None
        sev=df["ระดับอาการเฉลี่ย"].dropna().mean() if not df.empty else None
        meals=sum(len(x["meals"]) for x in records); meds=sum(len(x["medications"]) for x in records)
        cols=st.columns(3)
        cols[0].metric("วันที่มีบันทึก",days)
        cols[1].metric("วันที่รายงานเวียนศีรษะ",vertigo)
        cols[2].metric("เวลานอนเฉลี่ย",f"{sleep:.1f} ชม." if pd.notna(sleep) else "—")
        cols=st.columns(3)
        cols[0].metric("ระดับอาการเฉลี่ย",f"{sev:.1f}/10" if pd.notna(sev) else "—")
        cols[1].metric("รายการอาหาร",meals)
        cols[2].metric("รายการยา",meds)
        if not records: st.info("ยังไม่มีข้อมูลสุขภาพในช่วงเวลานี้ เริ่มต้นบันทึกวันแรกของคุณได้เลย")
        else:
            c1,c2=st.columns(2)
            with c1:
                fig=symptom_chart(df)
                if fig: st.plotly_chart(fig,use_container_width=True)
                else: st.info("ยังไม่มีข้อมูลระดับอาการเพียงพอสำหรับกราฟ")
            with c2:
                fig=sleep_chart(df)
                if fig: st.plotly_chart(fig,use_container_width=True)
                else: st.info("ยังไม่มีข้อมูลการนอนเพียงพอสำหรับกราฟ")
            st.caption("จำนวนรายการอาหารและยาเป็นจำนวนรายการที่บันทึก ไม่ใช่จำนวนครั้งที่รับประทาน")
    st.info("ข้อมูลและกราฟมีไว้ช่วยติดตามประวัติส่วนบุคคล ไม่ใช่การวินิจฉัยโรค")

elif page=="บันทึกประจำวัน":
    st.markdown("# บันทึกสุขภาพประจำวัน")
    st.caption("บันทึกเฉพาะข้อมูลที่ทราบได้ เลือกวันที่ย้อนหลังได้")
    selected=st.date_input("วันที่บันทึก",date.today(),key="journal_date")
    old=db.get_day(selected)
    with st.form("daily_form"):
        entry_time=st.time_input("เวลาที่บันทึก",value=time(9,0))
        note=st.text_area("หมายเหตุประจำวัน",value=(old or {}).get("daily_note") or "")
        tabs=st.tabs(["การนอน","เวียนศีรษะ","ปวดศีรษะ","ไลฟ์สไตล์"])
        with tabs[0]:
            old_s=(old or {}).get("sleep",{})
            c1,c2=st.columns(2)
            bed=c1.time_input("เวลาเข้านอน",value=time.fromisoformat(old_s["bed_time"]) if old_s.get("bed_time") else time(23,0))
            wake=c2.time_input("เวลาตื่นนอน",value=time.fromisoformat(old_s["wake_time"]) if old_s.get("wake_time") else time(7,0))
            duration=sleep_duration(bed,wake)
            st.caption(f"ระยะเวลาที่คำนวณได้: {duration:.2f} ชั่วโมง" if duration is not None else "กรอกเวลาเพื่อคำนวณระยะเวลานอน")
            quality=st.selectbox("คุณภาพการนอน (1–5)",[None,1,2,3,4,5],index=([None,1,2,3,4,5].index(old_s.get("quality")) if old_s.get("quality") in [1,2,3,4,5] else 0),format_func=lambda x:"ไม่ระบุ" if x is None else str(x))
            awaken=st.number_input("จำนวนครั้งที่ตื่นกลางดึก",min_value=0,step=1,value=int(old_s.get("awakenings") or 0))
            sleep_note=st.text_input("หมายเหตุการนอน",value=old_s.get("note") or "")
        with tabs[1]:
            ov=(old or {}).get("vertigo",{})
            has_v=st.checkbox("วันนี้มีอาการเวียนศีรษะ",value=bool(ov.get("has_symptom")))
            if has_v:
                v_sev=st.slider("ระดับความรุนแรง (0–10)",0,10,int(ov.get("severity") if ov.get("severity") is not None else 5))
                c1,c2=st.columns(2)
                v_time=c1.time_input("เวลาเริ่มมีอาการ",value=time.fromisoformat(ov["start_time"]) if ov.get("start_time") else time(12,0))
                v_dur=c2.number_input("ระยะเวลา (นาที)",min_value=0.0,value=float(ov.get("duration_minutes") or 0),step=5.0)
                v_type=st.multiselect("ลักษณะอาการ",["บ้านหมุน","โคลงเคลง","หน้ามืด","ไม่มั่นคง"],default=[x for x in (ov.get("symptom_type") or "").split(",") if x])
                v_activity=st.text_input("กิจกรรมขณะเริ่มมีอาการ",value=ov.get("activity") or "")
                v_assoc=st.text_input("อาการร่วม",value=ov.get("associated_symptoms") or "")
                v_factor=st.text_input("ปัจจัยที่สงสัยว่าอาจเกี่ยวข้อง",value=ov.get("suspected_factors") or "")
                v_note=st.text_area("หมายเหตุอาการเวียนศีรษะ",value=ov.get("note") or "")
            else:
                v_sev=v_time=v_dur=v_type=v_activity=v_assoc=v_factor=v_note=None
        with tabs[2]:
            oh=(old or {}).get("headache",{})
            has_h=st.checkbox("วันนี้มีอาการปวดศีรษะ",value=bool(oh.get("has_symptom")))
            if has_h:
                h_sev=st.slider("ระดับความรุนแรง (0–10)",0,10,int(oh.get("severity") if oh.get("severity") is not None else 5),key="hsev")
                h_loc=st.selectbox("ตำแหน่งที่ปวด",["ไม่ระบุ","หน้าผาก","ขมับ","ท้ายทอย","รอบศีรษะ","อื่น ๆ"],index=["ไม่ระบุ","หน้าผาก","ขมับ","ท้ายทอย","รอบศีรษะ","อื่น ๆ"].index(oh.get("location") or "ไม่ระบุ"))
                h_type=st.text_input("ลักษณะอาการปวด",value=oh.get("pain_type") or "")
                h_dur=st.number_input("ระยะเวลาที่ปวด (นาที)",min_value=0.0,value=float(oh.get("duration_minutes") or 0),step=5.0)
                h_assoc=st.text_input("อาการร่วม",value=oh.get("associated_symptoms") or "")
                h_note=st.text_area("หมายเหตุอาการปวดศีรษะ",value=oh.get("note") or "")
            else: h_sev=h_loc=h_type=h_dur=h_assoc=h_note=None
        with tabs[3]:
            ol=(old or {}).get("lifestyle",{})
            stress=st.slider("ระดับความเครียด (0–10)",0,10,int(ol.get("stress") or 0))
            fatigue=st.slider("ระดับความเหนื่อยล้า (0–10)",0,10,int(ol.get("fatigue") or 0))
            exercise=st.text_input("การออกกำลังกาย",value=ol.get("exercise") or "")
            screen=st.number_input("เวลาใช้หน้าจอ (ชั่วโมง)",min_value=0.0,value=float(ol.get("screen_hours") or 0),step=.5)
            water=st.number_input("ปริมาณน้ำดื่ม (มล.)",min_value=0.0,value=float(ol.get("water_ml") or 0),step=100.0)
            routine=st.text_input("การเปลี่ยนแปลงกิจวัตร",value=ol.get("routine_change") or "")
            life_note=st.text_area("หมายเหตุไลฟ์สไตล์",value=ol.get("note") or "")
        submitted=st.form_submit_button("บันทึกข้อมูล",use_container_width=True)
    if submitted:
        payload={"entry_date":selected,"entry_time":entry_time.isoformat(),"daily_note":note,
          "sleep":{"bed_time":bed.isoformat(),"wake_time":wake.isoformat(),"duration_hours":duration,"quality":quality,"awakenings":awaken or None,"note":sleep_note or None},
          "vertigo":{"has_symptom":int(has_v),"start_time":v_time.isoformat() if has_v else None,"duration_minutes":v_dur if has_v else None,"severity":v_sev if has_v else None,"symptom_type":",".join(v_type) if has_v else None,"activity":v_activity if has_v else None,"associated_symptoms":v_assoc if has_v else None,"suspected_factors":v_factor if has_v else None,"note":v_note if has_v else None},
          "headache":{"has_symptom":int(has_h),"severity":h_sev if has_h else None,"location":h_loc if has_h else None,"pain_type":h_type if has_h else None,"duration_minutes":h_dur if has_h else None,"associated_symptoms":h_assoc if has_h else None,"note":h_note if has_h else None},
          "lifestyle":{"stress":stress,"fatigue":fatigue,"exercise":exercise or None,"screen_hours":screen or None,"water_ml":water or None,"routine_change":routine or None,"note":life_note or None}}
        try:
            db.save_daily(payload); st.success("บันทึกสำเร็จแล้ว ข้อมูลถูกจัดเก็บในฐานข้อมูลของแอป")
            st.rerun()
        except Exception as e: st.error(f"ไม่สามารถบันทึกข้อมูลได้ กรุณาตรวจสอบข้อมูลอีกครั้ง ({type(e).__name__})")
    st.divider()
    st.subheader("เพิ่มอาหาร / เครื่องดื่ม หรือยา")
    eid=db.get_entry_id(selected)
    if not eid: st.info("บันทึกข้อมูลประจำวันก่อน จึงจะเพิ่มรายการอาหารหรือยาได้")
    else:
        with st.expander("เพิ่มอาหารและเครื่องดื่ม"):
            with st.form("meal_form"):
                c1,c2=st.columns(2)
                mt=c1.time_input("เวลา",time(8,0),key="meal_time")
                mealtype=c2.selectbox("มื้ออาหาร",["เช้า","กลางวัน","เย็น","ของว่าง","เครื่องดื่ม"],key="meal_type")
                item=st.text_input("ชื่ออาหารหรือเครื่องดื่ม")
                amount=st.text_input("ปริมาณโดยประมาณ")
                c1,c2=st.columns(2)
                caffeine=c1.selectbox("คาเฟอีน",["ไม่ระบุ","ไม่มี","มี"],key="caffeine")
                alcohol=c2.selectbox("แอลกอฮอล์",["ไม่ระบุ","ไม่มี","มี"],key="alcohol")
                water_meal=st.number_input("น้ำดื่ม (มล.)",min_value=0.0,step=100.0)
                mn=st.text_input("หมายเหตุ")
                if st.form_submit_button("เพิ่มรายการ"):
                    if item.strip():
                        db.add_meal(eid,{"meal_time":mt.isoformat(),"meal_type":mealtype,"item":item.strip(),"amount":amount,"caffeine":caffeine,"alcohol":alcohol,"water_ml":water_meal or None,"note":mn})
                        st.success("เพิ่มรายการอาหารแล้ว"); st.rerun()
                    else: st.warning("กรุณาระบุชื่ออาหารหรือเครื่องดื่ม")
        with st.expander("เพิ่มการใช้ยา"):
            with st.form("med_form"):
                name=st.text_input("ชื่อยา")
                dose=st.text_input("ขนาดยาตามที่ระบุ")
                taken=st.time_input("เวลาที่ใช้ยา",time(9,0),key="med_time")
                purpose=st.text_input("วัตถุประสงค์หรืออาการที่ต้องการบรรเทา")
                effect=st.text_input("ผลที่สังเกตหลังใช้ยา")
                adverse=st.text_input("อาการไม่พึงประสงค์ที่สังเกต")
                mednote=st.text_area("หมายเหตุ",key="med_note")
                if st.form_submit_button("เพิ่มยา"):
                    if name.strip():
                        db.add_medication(eid,{"name":name.strip(),"dose":dose,"taken_at":taken.isoformat(),"purpose":purpose,"observed_effect":effect,"adverse_effect":adverse,"note":mednote})
                        st.success("เพิ่มรายการยาแล้ว"); st.rerun()
                    else: st.warning("กรุณาระบุชื่อยา")


        day_now=db.get_day(selected)
        with st.expander("รายการอาหาร / เครื่องดื่มที่บันทึกไว้"):
            for m in day_now["meals"]:
                c1,c2=st.columns([5,1])
                c1.write(f'{m.get("meal_time") or ""} · {m.get("meal_type") or ""} · {m["item"]}')
                if c2.button("ลบ",key=f'del_meal_{m["id"]}'):
                    db.delete_child("meals",m["id"]); st.rerun()
        with st.expander("รายการยาที่บันทึกไว้"):
            for m in day_now["medications"]:
                c1,c2=st.columns([5,1])
                c1.write(f'{m.get("taken_at") or ""} · {m["name"]} · {m.get("dose") or "ไม่ระบุขนาด"}')
                if c2.button("ลบ",key=f'del_med_{m["id"]}'):
                    db.delete_child("medications",m["id"]); st.rerun()


elif page=="ปฏิทินและประวัติ":
    st.markdown("# ปฏิทินและประวัติ")
    chosen=st.date_input("เลือกวันที่ต้องการดู",date.today(),key="history_date")
    d=db.get_day(chosen)
    if d: show_day(d)
    else: st.info("ยังไม่มีข้อมูลในวันที่เลือก ลองเลือกวันอื่นหรือเริ่มบันทึกวันนี้ได้เลย")
    st.divider()
    st.subheader("รายการย้อนหลัง")
    c1,c2=st.columns(2)
    start=c1.date_input("ตั้งแต่วันที่",date.today()-timedelta(days=90),key="hist_start")
    end=c2.date_input("ถึงวันที่",date.today(),key="hist_end")
    records=db.list_history(start,end) if start<=end else []
    rows=[]
    for x in records:
        rows.append({"วันที่":x["entry_date"],"เวียนศีรษะ": "มี" if x["vertigo"].get("has_symptom") else "ไม่มี/ไม่ระบุ",
          "ปวดศีรษะ":"มี" if x["headache"].get("has_symptom") else "ไม่มี/ไม่ระบุ",
          "นอน (ชม.)":x["sleep"].get("duration_hours"),"อาหาร":len(x["meals"]),"ยา":len(x["medications"])})
    st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
    if records:
        del_date=st.selectbox("เลือกวันที่เพื่อลบข้อมูลทั้งวัน",[x["entry_date"] for x in records])
        if st.button("ลบข้อมูลวันที่เลือก",type="secondary"):
            st.session_state["confirm_delete"]=del_date
        if st.session_state.get("confirm_delete"):
            st.warning(f"ยืนยันการลบข้อมูลทั้งหมดของวันที่ {st.session_state['confirm_delete']} หรือไม่? การลบไม่สามารถย้อนกลับได้")
            c1,c2=st.columns(2)
            if c1.button("ยืนยันลบ",type="primary"):
                db.delete_day(st.session_state["confirm_delete"]); del st.session_state["confirm_delete"]; st.success("ลบข้อมูลแล้ว"); st.rerun()
            if c2.button("ยกเลิก"):
                del st.session_state["confirm_delete"]; st.rerun()

elif page=="วิเคราะห์อาการ":
    st.markdown("# วิเคราะห์รูปแบบจากบันทึก")
    start,end=date_range()
    if start and end:
        records=db.list_history(start,end); df=records_frame(records)
        if len(df)<2: st.info("ไม่พบข้อมูลเพียงพอสำหรับแสดงแนวโน้ม ลองบันทึกข้อมูลเพิ่มเติมในหลาย ๆ วัน")
        else:
            fig=symptom_chart(df)
            if fig: st.plotly_chart(fig,use_container_width=True)
            else: st.info("ไม่มีระดับอาการที่บันทึกในช่วงเวลานี้")
            fig=sleep_chart(df)
            if fig: st.plotly_chart(fig,use_container_width=True)
            for factor in ["ชั่วโมงนอน","ความเครียด"]:
                fig=correlation_chart(df,factor)
                if fig: st.plotly_chart(fig,use_container_width=True)
                else: st.caption(f"ข้อมูล {factor} และระดับอาการยังไม่เพียงพอ (ต้องมีอย่างน้อย 3 วันที่มีข้อมูลคู่กัน)")
            symptom_days=int(df["มีอาการ"].sum())
            st.write(f"พบวันที่มีการบันทึกอาการ {symptom_days} จาก {len(df)} วันที่มีบันทึก")
            st.caption("กราฟแสดงรูปแบบที่เกิดร่วมกันในข้อมูลที่บันทึก ไม่ได้ยืนยันความสัมพันธ์เชิงเหตุและผลหรือสาเหตุของอาการ")

elif page=="ส่งออก / นำเข้าข้อมูล":
    st.markdown("# ส่งออกและนำเข้าข้อมูล")
    st.write("ไฟล์จะถูกสร้างในเครื่องและไม่ถูกส่งไปยังบริการภายนอกโดยอัตโนมัติ")
    st.download_button("ดาวน์โหลดข้อมูลทั้งหมด (JSON)",db.export_json(),file_name="health_diary_export.json",mime="application/json")
    st.download_button("ดาวน์โหลดสรุป (CSV)",db.export_csv(),file_name="health_diary_summary.csv",mime="text/csv")
    st.warning("ก่อนนำเข้า JSON ควรสำรองฐานข้อมูลก่อน การนำเข้าวันที่ซ้ำอาจอัปเดตข้อมูลหลักของวันนั้น")
    uploaded=st.file_uploader("เลือกไฟล์ JSON ที่ส่งออกจาก Health Diary",type=["json"])
    if uploaded and st.button("นำเข้าข้อมูล"):
        try:
            count=db.import_json(uploaded.getvalue().decode("utf-8"))
            st.success(f"นำเข้าข้อมูล {count} วันแล้ว")
        except Exception as e: st.error(f"นำเข้าไม่สำเร็จ: {e}")

else:
    st.markdown("# ความเป็นส่วนตัวและข้อจำกัด")
    st.markdown("""
    - ข้อมูลจัดเก็บใน SQLite ภายในโฟลเดอร์ `data/health_diary.db` ของโปรเจกต์
    - แอปนี้ไม่ส่งข้อมูลสุขภาพไปยัง API ภายนอก
    - ฐานข้อมูลยัง **ไม่ได้เข้ารหัส** ผู้ที่เข้าถึงไฟล์เครื่องได้อาจอ่านข้อมูลได้
    - สำรองไฟล์ฐานข้อมูลเป็นระยะ และเก็บไฟล์สำรองในที่ปลอดภัย
    - การลบไฟล์ฐานข้อมูลอาจทำให้ข้อมูลสูญหายถาวร
    - หากนำแอปขึ้นออนไลน์ ต้องเพิ่มระบบยืนยันตัวตน การควบคุมสิทธิ์ HTTPS และมาตรการปกป้องข้อมูลก่อน
    """)
    st.warning("Health Diary เป็นเครื่องมือบันทึกและติดตามข้อมูลส่วนบุคคล ไม่ใช่เครื่องมือวินิจฉัยโรค ความสัมพันธ์ในกราฟไม่ได้ยืนยันเหตุและผล ไม่ควรเปลี่ยนยาโดยอาศัยแอปเพียงอย่างเดียว หากมีอาการรุนแรง ฉับพลัน หรือผิดปกติที่น่ากังวล ควรรับการประเมินจากบุคลากรทางการแพทย์")
