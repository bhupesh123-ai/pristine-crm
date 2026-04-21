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
import os
import datetime

def create_voucher_pdf(client_name, conf_no, hotel_details, check_in, check_out, nights, room_type, inclusions, notes):
    
    def clean(text):
        if not text: return ""
        return str(text).replace("•", "-").replace("‘", "'").replace("’", "'").replace("“", '"').replace("”", '"').replace("–", "-").replace("—", "-").encode('latin-1', 'ignore').decode('latin-1')

    # Clean all user inputs before printing
    client_name = clean(client_name)
    conf_no = clean(conf_no)
    hotel_details = clean(hotel_details)
    check_in = clean(check_in)
    check_out = clean(check_out)
    room_type = clean(room_type)
    inclusions = clean(inclusions)
    notes = clean(notes)

    pdf = FPDF('P', 'mm', 'A4')
    pdf.add_page()
    
    # --- Ultra-Minimal Palette ---
    GOLD = (186, 163, 104)       # Matte Champagne Gold
    LIGHT_GOLD = (250, 248, 242) # Extremely subtle gold-tinted grey
    DARK_TEXT = (40, 40, 40)
    GREY_TEXT = (100, 100, 100)

    # 1. Header (Fixed Logo Height & Spacing)
    if os.path.exists("logo.png"):
        # By setting 'h' instead of 'w', the logo anchors neatly at the top
        pdf.image("logo.png", x=10, y=10, h=25)

    # Right-aligned Company Details using Serif Font
    pdf.set_font("Times", "B", 18)
    pdf.set_text_color(*GOLD)
    pdf.set_xy(100, 12)
    pdf.multi_cell(100, 6, "PRISTINE VACATIONS", align="R")

    pdf.set_font("Times", "", 10)
    pdf.set_text_color(*GREY_TEXT)
    pdf.set_xy(100, 19)
    pdf.multi_cell(100, 5, "College Road, Ludhiana, India 141001\ninfo@pristine.in | www.pristinevacations.com", align="R")

    # Clean line pushed safely below the logo
    pdf.set_draw_color(*GOLD)
    pdf.line(10, 42, 200, 42)
    pdf.set_y(50)

    # 2. Main Title
    pdf.set_font("Times", "B", 15)
    pdf.set_text_color(*DARK_TEXT)
    pdf.cell(0, 8, "HOTEL ACCOMMODATION VOUCHER", ln=True, align="C")
    pdf.ln(6)

    # --- BLOCK 1: Conf & Status ---
    pdf.set_fill_color(*LIGHT_GOLD)
    pdf.set_font("Times", "B", 10)
    pdf.cell(95, 8, " CONFIRMATION NO.", fill=True)
    pdf.cell(95, 8, " BOOKING STATUS", fill=True, ln=True)

    pdf.set_font("Times", "", 11)
    pdf.cell(95, 8, f" {conf_no}", fill=True)
    pdf.set_font("Times", "B", 11)
    pdf.set_text_color(*GOLD)
    pdf.cell(95, 8, " Confirmed & Guaranteed", fill=True, ln=True)
    pdf.ln(5)

    # --- BLOCK 2: Guest & Property ---
    pdf.set_text_color(*DARK_TEXT)
    pdf.set_font("Times", "B", 10)
    pdf.cell(95, 8, " GUEST DETAILS", fill=True)
    pdf.cell(95, 8, " PROPERTY DETAILS", fill=True, ln=True)

    x = pdf.get_x()
    y = pdf.get_y()

    # Left Column: Guest
    pdf.set_xy(x+2, y+2)
    pdf.set_font("Times", "B", 12)
    pdf.cell(90, 6, client_name, ln=True)
    pdf.set_font("Times", "", 10)
    pdf.set_x(x+2)
    pdf.cell(90, 5, f"Confirmation Date: {datetime.date.today().strftime('%d %b %Y')}", ln=True)

    # Right Column: Property
    pdf.set_xy(x+97, y+2)
    pdf.set_font("Times", "", 11)
    pdf.multi_cell(90, 6, hotel_details)

    pdf.set_y(max(pdf.get_y(), y + 15) + 6)

    # --- BLOCK 3: Dates ---
    pdf.set_fill_color(*GOLD)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Times", "B", 10)
    pdf.cell(63, 8, "CHECK-IN", fill=True, align="C")
    pdf.cell(64, 8, "NIGHTS", fill=True, align="C")
    pdf.cell(63, 8, "CHECK-OUT", fill=True, align="C", ln=True)

    pdf.set_text_color(*DARK_TEXT)
    pdf.set_font("Times", "", 12)
    pdf.cell(63, 10, check_in, align="C")
    pdf.cell(64, 10, str(nights), align="C")
    pdf.cell(63, 10, check_out, align="C", ln=True)
    pdf.ln(6)

    # --- BLOCK 4: Room & Inclusions ---
    pdf.set_fill_color(*LIGHT_GOLD)
    pdf.set_font("Times", "B", 10)
    pdf.cell(95, 8, " ROOM CATEGORY", fill=True)
    pdf.cell(95, 8, " INCLUSIONS", fill=True, ln=True)

    x = pdf.get_x()
    y = pdf.get_y()

    pdf.set_font("Times", "", 11)
    pdf.set_xy(x+2, y+2)
    pdf.multi_cell(90, 6, room_type)
    y_room = pdf.get_y()

    pdf.set_xy(x+97, y+2)
    pdf.multi_cell(90, 6, inclusions)
    y_inc = pdf.get_y()

    pdf.set_y(max(y_room, y_inc) + 8)

    # --- BLOCK 5: Notes & Info ---
    if notes.strip():
        pdf.set_font("Times", "B", 10)
        pdf.cell(0, 6, "ARRIVAL & SPECIAL NOTES:", ln=True)
        pdf.set_font("Times", "", 10)
        pdf.multi_cell(0, 6, notes)
        pdf.ln(6)

    pdf.set_font("Times", "B", 10)
    pdf.cell(0, 6, "IMPORTANT INFORMATION:", ln=True)
    pdf.set_font("Times", "", 10)
    safe_info = "- Please present this voucher and a valid Passport upon arrival.\n- Standard check-in time is 14:00 hrs and check-out is 12:00 hrs.\n- Incidental charges to be settled directly with the hotel."
    pdf.multi_cell(0, 6, safe_info)

    # --- Footer ---
    pdf.ln(15)
    pdf.set_draw_color(*GOLD)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(5)
    pdf.set_font("Times", "I", 10)
    pdf.set_text_color(*GOLD)
    
    pdf.cell(0, 5, "Discover Luxury | www.discoverluxury.in | www.pristinevacations.com", align="C")

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
