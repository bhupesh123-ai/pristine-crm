import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Text, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
import datetime
import os
import time

# Official Google Library
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable

# ===============================
# 1. PAGE CONFIGURATION
# ===============================
st.set_page_config(page_title="Pristine Vacations CRM", page_icon="✈️", layout="wide")

# ===============================
# 2. DATABASE SETUP
# ===============================
DATABASE_URL = "sqlite:///pristine_crm.db"
Base = declarative_base()
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
db_session = SessionLocal()

# ===============================
# 3. DATABASE MODELS
# ===============================
class Lead(Base):
    __tablename__ = "leads"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    email = Column(String)
    phone = Column(String)
    source = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    queries = relationship("Query", back_populates="lead")

class Query(Base):
    __tablename__ = "queries"
    id = Column(Integer, primary_key=True)
    lead_id = Column(Integer, ForeignKey("leads.id"))
    destination = Column(String)
    travel_date = Column(String)
    pax = Column(Integer)
    budget = Column(String)
    notes = Column(Text)
    
    # --- STAFF WORKFLOW FIELDS ---
    status = Column(String, default="Pending")
    saved_itinerary = Column(Text, default="")
    saved_hotels = Column(Text, default="")
    saved_price = Column(Text, default="")
    
    lead = relationship("Lead", back_populates="queries")

Base.metadata.create_all(bind=engine)

# Try loading PDF Maker
try:
    from pdf_maker import create_itinerary_pdf
except ImportError:
    pass # Will handle gracefully in the UI

from fpdf import FPDF

def create_voucher_pdf(client_name, ref_number, service_type, dates, details_text):
    pdf = FPDF()
    pdf.add_page()
    
    # 1. Add Logo (if it exists in the folder)
    if os.path.exists("logo.png"):
        pdf.image("logo.png", x=10, y=8, w=50)
    
    # Header
    pdf.set_font("Arial", "B", 20)
    pdf.cell(0, 20, "CONFIRMATION VOUCHER", ln=True, align="R")
    pdf.ln(10)
    
    # Client Info Block
    pdf.set_fill_color(240, 240, 240) # Light grey background
    pdf.set_font("Arial", "B", 12)
    pdf.cell(40, 10, "Client Name:", border=1, fill=True)
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 10, f" {client_name}", border=1, ln=True)
    
    pdf.set_font("Arial", "B", 12)
    pdf.cell(40, 10, "Booking Ref:", border=1, fill=True)
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 10, f" {ref_number}", border=1, ln=True)

    pdf.set_font("Arial", "B", 12)
    pdf.cell(40, 10, "Travel Dates:", border=1, fill=True)
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 10, f" {dates}", border=1, ln=True)
    
    pdf.set_font("Arial", "B", 12)
    pdf.cell(40, 10, "Service Type:", border=1, fill=True)
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 10, f" {service_type}", border=1, ln=True)
    
    pdf.ln(10)
    
    # Main Voucher Text
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, "Service & Confirmation Details:", ln=True)
    pdf.set_font("Arial", "", 11)
    
    # Multi_cell allows the text to wrap to the next line naturally
    pdf.multi_cell(0, 7, details_text)
    
    pdf.ln(20)
    
    # Footer
    pdf.set_font("Arial", "I", 10)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 10, "Thank you for booking with Pristine Vacations. Wishing you a wonderful trip!", align="C", ln=True)
    pdf.cell(0, 10, "Emergency Contact: +91 [YOUR NUMBER] | Email: [YOUR EMAIL]", align="C")
    
    # Output as a byte string for Streamlit download
    return pdf.output(dest="S").encode("latin-1")
    
# ===============================
# 4. OFFICIAL GOOGLE AI ENGINE (SECRETS ONLY)
# ===============================
def generate_itinerary_free(prompt_text):
    # 1. Securely load API Key from Streamlit Secrets
    try:
        clean_key = st.secrets["GOOGLE_API_KEY"].strip()
    except Exception:
        return None, "API Key is missing. Please ensure it is added to Streamlit Secrets."

    if not clean_key:
        return None, "API Key is empty in Secrets."

    genai.configure(api_key=clean_key)
    
    # 2. AUTO-DISCOVERY: Find the best model available to this key
    try:
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        chosen_model = None
        # We look for your specific shiny new Gemini 2.5 and 2.0 models
        for preferred in [
            'models/gemini-2.5-flash', 
            'models/gemini-2.0-flash',
            'models/gemini-flash-latest',
            'models/gemini-2.5-pro',
            'models/gemini-pro-latest'
        ]:
            if preferred in available_models:
                chosen_model = preferred
                break
                
        if not chosen_model:
            return None, "Your API key does not have access to any text generation models."
            
    except Exception as e:
        return None, f"Failed to connect to Google: {str(e)}"

    # 3. Configure the chosen model (THIS IS THE LINE THAT WENT MISSING!)
    clean_model_name = chosen_model.replace('models/', '')
    model = genai.GenerativeModel(clean_model_name)

    # 4. Generate with Auto-Retries (Bypasses 503 & 429 errors)
    for attempt in range(3):
        try:
            response = model.generate_content(prompt_text)
            return response.text, f"Success (Used: {clean_model_name})"
            
        except ResourceExhausted:
            print(f"Quota hit. Waiting 5 seconds (Attempt {attempt+1}/3)...")
            time.sleep(5)
            continue
            
        except ServiceUnavailable:
            print(f"Server busy. Waiting 5 seconds (Attempt {attempt+1}/3)...")
            time.sleep(5)
            continue
            
        except Exception as e:
            return None, f"Google Error: {str(e)}"

    return None, "Google's servers are too busy right now. Please wait 30 seconds and try again."

# ===============================
# 5. SIDEBAR & NAVIGATION
# ===============================
if os.path.exists("logo.png"):
    st.sidebar.image("logo.png", width=200)

st.sidebar.title("Navigation")
menu = st.sidebar.radio("Go to:", ["Dashboard", "New Enquiry", "AI Itinerary Builder", "Voucher Generator"])

# ===============================
# PAGE: DASHBOARD
# ===============================
if menu == "Dashboard":
    st.title("📊 Agency Dashboard")
    leads = db_session.query(Lead).all()
    queries = db_session.query(Query).all()
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Leads", len(leads))
    c2.metric("Active Queries", len(queries))
    
    quoted = len([q for q in queries if q.status == "Quoted"])
    c3.metric("Quotes Sent", quoted)
    c4.metric("Pending", len(queries) - quoted)

    st.markdown("---")
    st.subheader("Active Queries")
    
    if queries:
        data = []
        for q in queries:
            data.append({
                "Client": q.lead.name,
                "Destination": q.destination,
                "Travel Date": q.travel_date,
                "Status": q.status,
                "Last Saved": "✅" if q.saved_itinerary else "❌"
            })
        st.dataframe(pd.DataFrame(data), use_container_width=True)
    else:
        st.info("No queries found.")

# ===============================
# PAGE: NEW ENQUIRY
# ===============================
elif menu == "New Enquiry":
    st.title("📝 New Booking Enquiry")
    with st.form("lead_form"):
        c1, c2 = st.columns(2)
        name = c1.text_input("Client Name")
        phone = c2.text_input("Phone Number")
        email = c1.text_input("Email")
        source = c2.selectbox("Source", ["Instagram", "Referral", "Website", "Walk-in"])
        st.markdown("---")
        st.subheader("Trip Details")
        dest = st.text_input("Destination")
        travel_date = st.date_input("Travel Date")
        pax = st.number_input("No. of Pax", min_value=1)
        budget = st.text_input("Budget (Approx)")
        notes = st.text_area("Requirements / Notes")
        
        if st.form_submit_button("Save Enquiry"):
            if name and dest:
                new_lead = Lead(name=name, email=email, phone=phone, source=source)
                db_session.add(new_lead)
                db_session.commit()
                new_query = Query(lead_id=new_lead.id, destination=dest, travel_date=str(travel_date), pax=pax, budget=budget, notes=notes)
                db_session.add(new_query)
                db_session.commit()
                st.success(f"✅ Saved! Lead ID: {new_lead.id}")
            else:
                st.error("⚠️ Name and Destination are required.")

# ===============================
# PAGE: AI ITINERARY BUILDER
# ===============================
elif menu == "AI Itinerary Builder":
    st.header("✨ Smart Itinerary Creator")
    
    queries = db_session.query(Query).all()
    if not queries:
        st.info("No enquiries found. Please add a lead first.")
        st.stop()

    query_options = {f"{q.id}: {q.lead.name} ({q.destination})": q for q in queries}
    selected_query_label = st.selectbox("Select Client", list(query_options.keys()))
    
    if selected_query_label:
        selected_query = query_options[selected_query_label]

        if 'current_query_id' not in st.session_state or st.session_state['current_query_id'] != selected_query.id:
            st.session_state['current_query_id'] = selected_query.id
            st.session_state['generated_itinerary'] = selected_query.saved_itinerary or ""
            st.session_state['saved_hotels'] = selected_query.saved_hotels or "Option 1: Hilton (BB)\nOption 2: Marriott (BB)"
            st.session_state['saved_price'] = selected_query.saved_price or "Total Cost: INR 1,50,000"

        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Trip Start Date")
            split_stay = st.text_input("Structure", placeholder="e.g. 3N Mara, 1N Nairobi")
        with col2:
            sightseeing = st.text_area("Major Sightseeing", placeholder="e.g. Museum of the Future")

        st.info("✈️ Paste Flight PNR below (AI will extract times)")
        pnr_text = st.text_area("Flight Details", height=70)

        if st.button("Generate Draft Itinerary", type="primary"):
            with st.spinner("Connecting to Google (Secure Secrets)..."):
                prompt = f"""
                Act as a Senior Consultant for Pristine Vacations.
                Create a structured itinerary for {selected_query.destination}.
                DETAILS:
                - Start Date: {start_date}
                - Structure: {split_stay}
                - Flight PNR: "{pnr_text}"
                - Highlights: {sightseeing}
                STRICT FORMATTING RULE:
                For each day, write the header in this specific format:
                "Day X: [Date] - [MAJOR HIGHLIGHT]"
                Tone: Professional & Exciting.
                """
                
                result_text, status_msg = generate_itinerary_free(prompt)
                
                if result_text:
                    st.session_state['generated_itinerary'] = result_text
                    st.success(f"✅ {status_msg}")
                    selected_query.saved_itinerary = result_text
                    selected_query.status = "Draft Generated"
                    db_session.commit()
                    st.rerun()
                else:
                    st.error(f"❌ Generation Failed.\n\nDetails:\n{status_msg}")

        if st.session_state['generated_itinerary']:
            st.markdown("---")
            st.subheader("1. Itinerary Content")
            final_text = st.text_area("Edit Itinerary:", value=st.session_state['generated_itinerary'], height=500)
            
            col_a, col_b = st.columns(2)
            with col_a:
                st.subheader("2. Accommodation")
                hotel_text = st.text_area("Enter Hotel Details:", value=st.session_state['saved_hotels'], height=200)
            with col_b:
                st.subheader("3. Investment")
                price_text = st.text_area("Enter Final Price:", value=st.session_state['saved_price'], height=200)
            
            c1, c2 = st.columns(2)
            
            with c1:
                if st.button("💾 Save Progress"):
                    selected_query.saved_itinerary = final_text
                    selected_query.saved_hotels = hotel_text
                    selected_query.saved_price = price_text
                    selected_query.status = "Work in Progress"
                    db_session.commit()
                    st.success("✅ Work Saved to Database!")
            
            with c2:
                if st.button("📄 Finalize & Download PDF"):
                    selected_query.saved_itinerary = final_text
                    selected_query.saved_hotels = hotel_text
                    selected_query.saved_price = price_text
                    selected_query.status = "Quoted" 
                    db_session.commit()
                    
                    try:
                        pdf_data = create_itinerary_pdf(selected_query.lead.name, selected_query.destination, final_text, hotel_text, price_text)
                        st.download_button(label="Click to Save PDF", data=pdf_data, file_name=f"Quote_{selected_query.lead.name}.pdf", mime="application/pdf")
                    except Exception as e:
                        st.error("Cannot create PDF. Ensure 'pdf_maker.py' is in the same folder.")


    # ===============================
# PAGE: VOUCHER GENERATOR
# ===============================
elif menu == "Voucher Generator":
    st.header("🎟️ Standardized Voucher Generator")
    st.write("Generate a quick PDF confirmation voucher for your clients.")
    
    with st.container(border=True):
        col1, col2 = st.columns(2)
        
        with col1:
            v_client = st.text_input("Client Name", placeholder="e.g., Mr. Pankaj Kashyap")
            v_ref = st.text_input("Booking Reference / PNR", placeholder="e.g., PRIS-88392")
            
        with col2:
            v_service = st.selectbox("Service Type", ["Flight Ticket", "Hotel Accommodation", "Complete Package", "Transfer/Sightseeing"])
            v_dates = st.text_input("Travel Dates", placeholder="e.g., 12 Oct 2026 - 15 Oct 2026")

        st.markdown("---")
        st.subheader("Voucher Details")
        st.caption("Paste the hotel confirmation, flight times, or inclusions here.")
        
        default_text = """Hotel Name: 
Check-in: 
Check-out: 
Room Type: 
Meal Plan: 

Confirmation Number: 
Status: CONFIRMED

Important Notes:
- Please present a valid ID at the time of check-in.
- Standard check-in time is 14:00 hrs."""
        
        v_details = st.text_area("Details", value=default_text, height=250)
        
        if st.button("📄 Generate Voucher PDF", type="primary"):
            if v_client and v_ref:
                try:
                    pdf_bytes = create_voucher_pdf(v_client, v_ref, v_service, v_dates, v_details)
                    st.success("Voucher generated successfully!")
                    
                    st.download_button(
                        label="⬇️ Download Voucher PDF",
                        data=pdf_bytes,
                        file_name=f"Voucher_{v_client.replace(' ', '_')}.pdf",
                        mime="application/pdf"
                    )
                except Exception as e:
                    st.error(f"Error generating PDF: {str(e)}. Make sure 'fpdf' is installed.")
            else:
                st.warning("Please enter the Client Name and Booking Reference.")
