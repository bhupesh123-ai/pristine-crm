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

def create_voucher_pdf(client_name, conf_no, hotel_details, check_in, check_out, nights, room_type, inclusions, notes):
    pdf = FPDF('P', 'mm', 'A4')
    pdf.add_page()
    
    # Brand Colors
    PRIMARY = (41, 128, 185)   # Pristine Blue
    DARK_BG = (41, 128, 185)   # Table Header Blue
    LIGHT_BG = (236, 240, 241) # Light Grey Fill
    TEXT = (40, 40, 40)        # Dark Grey Text

    # 1. Header (Logo & Company Info)
    if os.path.exists("logo.png"):
        pdf.image("logo.png", x=10, y=10, w=40)

    pdf.set_font("Arial", "B", 15)
    pdf.set_text_color(*PRIMARY)
    pdf.set_xy(60, 12)
    pdf.cell(0, 6, "PRISTINE VACATIONS", ln=True)

    pdf.set_font("Arial", "", 9)
    pdf.set_text_color(*TEXT)
    pdf.set_x(60)
    pdf.cell(0, 5, "College Road, Ludhiana, India 141001", ln=True)
    pdf.set_x(60)
    pdf.cell(0, 5, "Email: info@pristine.in | Website: www.pristinevacations.com", ln=True)

    pdf.line(10, 32, 200, 32)
    pdf.ln(10)

    # 2. Main Title
    pdf.set_font("Arial", "B", 14)
    pdf.set_text_color(*PRIMARY)
    pdf.cell(0, 10, "HOTEL VOUCHER", ln=True, align="C")
    pdf.ln(2)

    # --- BLOCK 1: Conf & Status ---
    pdf.set_font("Arial", "B", 9)
    pdf.set_fill_color(*LIGHT_BG)
    pdf.set_text_color(*TEXT)
    pdf.cell(95, 7, " HOTEL CONFIRMATION NO.", border=1, fill=True)
    pdf.cell(95, 7, " BOOKING STATUS", border=1, fill=True, ln=True)

    pdf.set_font("Arial", "", 10)
    pdf.cell(95, 8, f" {conf_no}", border=1)
    pdf.set_font("Arial", "B", 10)
    pdf.cell(95, 8, " Confirmed & Guaranteed", border=1, ln=True)
    pdf.ln(4)

    # --- BLOCK 2: Property & Lead Passenger ---
    pdf.set_font("Arial", "B", 9)
    pdf.set_fill_color(*LIGHT_BG)
    pdf.cell(95, 7, " PROPERTY DETAILS", border=1, fill=True)
    pdf.cell(95, 7, " LEAD PASSENGER", border=1, fill=True, ln=True)

    pdf.set_font("Arial", "", 9)
    x = pdf.get_x()
    y = pdf.get_y()

    # Draw strict borders for clean alignment
    pdf.rect(x, y, 95, 18)
    pdf.rect(x+95, y, 95, 18)

    pdf.set_xy(x+2, y+2)
    pdf.multi_cell(90, 5, hotel_details)

    pdf.set_xy(x+97, y+2)
    pdf.set_font("Arial", "B", 10)
    pdf.cell(90, 5, client_name, ln=True)
    pdf.set_font("Arial", "", 9)
    pdf.set_x(x+97)
    pdf.cell(90, 5, f"Confirmation Date: {datetime.date.today().strftime('%d %b %Y')}", ln=True)

    pdf.set_y(y + 18 + 4)

    # --- BLOCK 3: Dates ---
    pdf.set_font("Arial", "B", 9)
    pdf.set_fill_color(*DARK_BG)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(63, 7, "CHECK-IN", border=1, fill=True, align="C")
    pdf.cell(64, 7, "NIGHTS", border=1, fill=True, align="C")
    pdf.cell(63, 7, "CHECK-OUT", border=1, fill=True, align="C", ln=True)

    pdf.set_font("Arial", "B", 11)
    pdf.set_text_color(*TEXT)
    pdf.cell(63, 9, check_in, border=1, align="C")
    pdf.cell(64, 9, str(nights), border=1, align="C")
    pdf.cell(63, 9, check_out, border=1, align="C", ln=True)
    pdf.ln(4)

    # --- BLOCK 4: Arrival Info ---
    pdf.set_font("Arial", "B", 9)
    pdf.set_fill_color(*LIGHT_BG)
    pdf.cell(0, 7, " ARRIVAL INFORMATION & NOTES:", border=1, fill=True, ln=True)
    pdf.set_font("Arial", "", 9)
    pdf.multi_cell(0, 6, f" {notes}", border=1)
    pdf.ln(4)

    # --- BLOCK 5: Guest & Room (The Table) ---
    pdf.set_font("Arial", "B", 9)
    pdf.set_fill_color(*LIGHT_BG)
    pdf.cell(63, 7, " GUEST NAME", border=1, fill=True)
    pdf.cell(64, 7, " ROOM CATEGORY", border=1, fill=True)
    pdf.cell(63, 7, " INCLUSIONS", border=1, fill=True, ln=True)

    pdf.set_font("Arial", "", 9)
    x = pdf.get_x()
    y = pdf.get_y()
    
    pdf.rect(x, y, 63, 25)
    pdf.rect(x+63, y, 64, 25)
    pdf.rect(x+127, y, 63, 25)

    pdf.set_xy(x+2, y+2)
    pdf.multi_cell(59, 5, client_name)

    pdf.set_xy(x+65, y+2)
    pdf.multi_cell(60, 5, room_type)

    pdf.set_xy(x+129, y+2)
    pdf.multi_cell(59, 5, inclusions)

    pdf.set_y(y + 25 + 8)

    # --- BLOCK 6: Important Info ---
    pdf.set_font("Arial", "B", 10)
    pdf.cell(0, 6, "Important Information:", ln=True)
    pdf.set_font("Arial", "", 9)
    pdf.multi_cell(0, 5, "• Please present this voucher and a valid Passport upon arrival.\n• Standard check-in time is 14:00 hrs and check-out is 12:00 hrs.\n• Incidental charges to be settled directly with the hotel.")

    pdf.ln(15)
    pdf.set_font("Arial", "I", 9)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 5, "Luxury Travel Designed by Pristine Vacations | www.pristinevacations.com", align="C")

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
# PAGE: PREMIUM VOUCHER GENERATOR
# ===============================
elif menu == "Voucher Generator":
    st.header("🎟️ Premium Hotel Voucher")
    st.write("Generate a beautifully formatted hotel confirmation voucher.")

    with st.container(border=True):
        st.subheader("1. Guest & Booking Details")
        c1, c2, c3 = st.columns(3)
        v_client = c1.text_input("Lead Passenger Name", placeholder="e.g. Mr. Arjun Singh Rawat")
        v_conf = c2.text_input("Hotel Confirmation No.", placeholder="e.g. TBR7CNFIWO50...")
        v_hotel = c3.text_area("Property Name & Address", height=68, placeholder="Citadines Sukhumvit 11\nBangkok 10110, Thailand")

        st.subheader("2. Travel Dates")
        d1, d2, d3 = st.columns(3)
        v_in = d1.date_input("Check-In Date")
        v_out = d2.date_input("Check-Out Date")

        # Calculate total nights automatically
        nights = 0
        if v_in and v_out:
            nights = (v_out - v_in).days
            if nights < 0: nights = 0
            
        d3.metric("Total Nights", nights)

        st.subheader("3. Room & Inclusions")
        r1, r2 = st.columns(2)
        v_room = r1.text_area("Room Category", placeholder="Studio Executive\n30 sqm | Queen Bed", height=100)
        v_inc = r2.text_area("Inclusions", placeholder="Daily Breakfast\nFree WiFi", height=100)

        v_notes = st.text_input("Arrival Information & Notes", placeholder="Arrival on 20th April at 05:00 HRS. Room is pre-booked...")

        if st.button("📄 Generate Premium Voucher", type="primary"):
            if v_client and v_conf and v_hotel:
                # Format dates to string "19 Apr 2026"
                in_str = v_in.strftime("%d %b %Y")
                out_str = v_out.strftime("%d %b %Y")

                try:
                    pdf_bytes = create_voucher_pdf(
                        client_name=v_client,
                        conf_no=v_conf,
                        hotel_details=v_hotel,
                        check_in=in_str,
                        check_out=out_str,
                        nights=nights,
                        room_type=v_room,
                        inclusions=v_inc,
                        notes=v_notes
                    )
                    st.success("Premium Voucher generated successfully!")

                    st.download_button(
                        label="⬇️ Download Premium Voucher",
                        data=pdf_bytes,
                        file_name=f"Hotel_Voucher_{v_client.replace(' ', '_')}.pdf",
                        mime="application/pdf"
                    )
                except Exception as e:
                    st.error(f"Error generating PDF: {str(e)}")
            else:
                st.warning("⚠️ Please fill in the Lead Passenger, Confirmation No, and Property Details.")
