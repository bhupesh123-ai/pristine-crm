import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Text, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
import datetime
import os
import requests
import json
import time

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
# 3. API KEY LOADING (HARDCODED FOR TESTING)
# ===============================
# Paste your NEW key exactly between the quotes below:
GOOGLE_KEY = "AIzaSyCCWXJ9461pr-t4PVe5rYAmbfbcExJZ20o"

# ===============================
# 4. UPGRADED DATABASE MODELS
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
    
    # --- NEW FIELDS FOR STAFF WORKFLOW ---
    status = Column(String, default="Pending")  # Pending, Quoted, Confirmed, Lost
    saved_itinerary = Column(Text, default="")  # Saves the AI text
    saved_hotels = Column(Text, default="")     # Saves the hotel block
    saved_price = Column(Text, default="")      # Saves the price block
    
    lead = relationship("Lead", back_populates="queries")

Base.metadata.create_all(bind=engine)

try:
    from pdf_maker import create_itinerary_pdf
except ImportError:
    st.error("CRITICAL: 'pdf_maker.py' file missing.")
    st.stop()


# ===============================
# 5. OFFICIAL GOOGLE AI ENGINE (SELF-HEALING)
# ===============================
import time
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable

def generate_itinerary_free(prompt_text):
    # 1. Load and clean the API key
    try:
        clean_key = st.secrets["GOOGLE_API_KEY"].strip()
    except:
        # Paste your key below for testing
        clean_key = "PASTE_YOUR_KEY_HERE".strip() 

    if not clean_key or clean_key == "PASTE_YOUR_KEY_HERE":
        return None, "API Key is missing."

    genai.configure(api_key=clean_key)
    
    # 2. AUTO-DISCOVERY: Ask Google what models this key is allowed to use
    try:
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        # Priority list (it will pick the best one your key has access to)
        chosen_model = None
        for preferred in ['models/gemini-1.5-flash', 'models/gemini-1.5-flash-latest', 'models/gemini-1.0-pro', 'models/gemini-pro']:
            if preferred in available_models:
                chosen_model = preferred
                break
                
        if not chosen_model:
            return None, "Your API key does not have access to any text generation models."
            
    except Exception as e:
        return None, f"Failed to connect to Google: {str(e)}"

    # 3. Configure the chosen model
    # Strip the 'models/' prefix because the library adds it automatically
    clean_model_name = chosen_model.replace('models/', '')
    model = genai.GenerativeModel(clean_model_name)

    # 4. Generate with Auto-Retries
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
# 6. SIDEBAR & NAVIGATION
# ===============================
if os.path.exists("logo.png"):
    st.sidebar.image("logo.png", width=200)

st.sidebar.title("Navigation")
menu = st.sidebar.radio("Go to:", ["Dashboard", "New Enquiry", "AI Itinerary Builder"])

# ===============================
# PAGE: DASHBOARD
# ===============================
if menu == "Dashboard":
    st.title("📊 Agency Dashboard")
    leads = db_session.query(Lead).all()
    queries = db_session.query(Query).all()
    
    # METRICS
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Leads", len(leads))
    c2.metric("Active Queries", len(queries))
    
    # Calculate Conversion
    quoted = len([q for q in queries if q.status == "Quoted"])
    c3.metric("Quotes Sent", quoted)
    c4.metric("Pending", len(queries) - quoted)

    st.markdown("---")
    st.subheader("Active Queries")
    
    if queries:
        # Custom Table with Status
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
# PAGE: AI ITINERARY BUILDER (STAFF WORKFLOW)
# ===============================
elif menu == "AI Itinerary Builder":
    st.header("✨ Smart Itinerary Creator")
    
    # Load Queries
    queries = db_session.query(Query).all()
    if not queries:
        st.info("No enquiries found. Please add a lead first.")
        st.stop()

    # Dropdown to Select Client
    query_options = {f"{q.id}: {q.lead.name} ({q.destination})": q for q in queries}
    selected_query_label = st.selectbox("Select Client", list(query_options.keys()))
    
    if selected_query_label:
        selected_query = query_options[selected_query_label]

        # --- LOAD SAVED DATA (If exists) ---
        # If the user has saved data in DB, load it into session state
        if 'current_query_id' not in st.session_state or st.session_state['current_query_id'] != selected_query.id:
            st.session_state['current_query_id'] = selected_query.id
            st.session_state['generated_itinerary'] = selected_query.saved_itinerary or ""
            st.session_state['saved_hotels'] = selected_query.saved_hotels or "Option 1: Hilton (BB)\nOption 2: Marriott (BB)"
            st.session_state['saved_price'] = selected_query.saved_price or "Total Cost: INR 1,50,000"

        # --- INPUTS ---
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Trip Start Date")
            split_stay = st.text_input("Structure", placeholder="e.g. 3N Mara, 1N Nairobi")
        with col2:
            sightseeing = st.text_area("Major Sightseeing", placeholder="e.g. Museum of the Future")

        st.info("✈️ Paste Flight PNR below (AI will extract times)")
        pnr_text = st.text_area("Flight Details", height=70)

        # --- GENERATE BUTTON ---
        if st.button("Generate Draft Itinerary", type="primary"):
            if not GOOGLE_KEY:
                st.error("❌ API Key Not Found in secrets.toml.")
            else:
                with st.spinner("Connecting to Google (Free Tier)..."):
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
                        # Auto-save raw output to DB so we don't lose it
                        selected_query.saved_itinerary = result_text
                        selected_query.status = "Draft Generated"
                        db_session.commit()
                        st.rerun()
                    else:
                        st.error(f"❌ Generation Failed.\n\nDetails:\n{status_msg}")

        # --- EDITOR & SAVING ---
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
            
            # --- ACTION BUTTONS ---
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
                    # Save first
                    selected_query.saved_itinerary = final_text
                    selected_query.saved_hotels = hotel_text
                    selected_query.saved_price = price_text
                    selected_query.status = "Quoted"  # Mark as done
                    db_session.commit()
                    
                    # Generate PDF
                    pdf_data = create_itinerary_pdf(selected_query.lead.name, selected_query.destination, final_text, hotel_text, price_text)
                    st.download_button(label="Click to Save PDF", data=pdf_data, file_name=f"Quote_{selected_query.lead.name}.pdf", mime="application/pdf")
