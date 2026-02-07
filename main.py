import streamlit as st
import google.generativeai as genai
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from models import Base, Query, Lead, Itinerary, User  # Importing your database structure
from datetime import datetime
import pandas as pd
from pdf_maker import create_itinerary_pdf
# --- CONFIGURATION ---
st.set_page_config(page_title="Pristine Vacations CRM", layout="wide", page_icon="✈️")

# Connect to the Database
engine = create_engine('sqlite:///pristine_crm.db')
Session = sessionmaker(bind=engine)
db_session = Session()


# --- SIDEBAR (Settings) ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3125/3125848.png", width=50)
    st.title("Pristine Vacations")
    st.markdown("---")
    menu = st.radio("Navigation", ["Dashboard", "New Enquiry", "AI Itinerary Builder"])

    st.markdown("---")

    # SMART KEY HANDLING
    if "GOOGLE_API_KEY" in st.secrets:
        api_key = st.secrets["GOOGLE_API_KEY"]
        st.success("✅ AI System Connected")

    elif "api_key" in st.session_state:
        api_key = st.session_state.api_key
        st.success("✅ AI Key Active")

    else:
        api_key = st.text_input("Enter Gemini API Key", type="password")
        if api_key:
            st.session_state.api_key = api_key
            st.rerun()

    if api_key:
        genai.configure(api_key=api_key)

# --- PAGE 1: DASHBOARD ---
if menu == "Dashboard":
    st.header("📊 Office Dashboard")
    
    # Fetch data from YOUR Real Database
    queries = db_session.query(Query).all()
    
    if queries:
        data = []
        for q in queries:
            data.append({
                "ID": q.id,
                "Guest": q.lead.name if q.lead else "Unknown",
                "Destination": q.destination,
               "Status": q.status,  
                "Date": q.created_at.strftime("%Y-%m-%d")
            })
        st.dataframe(pd.DataFrame(data), use_container_width=True)
    else:
        st.info("No enquiries yet. Go to 'New Enquiry' to add one.")


# --- PAGE 2: NEW ENQUIRY (FAST ENTRY VERSION) ---
elif menu == "New Enquiry":
    st.header("📝 Create New Enquiry")
    
    with st.form("new_enquiry_form"):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Client Name (Required)")
            phone = st.text_input("Phone Number")
            email = st.text_input("Email Address")
        with col2:
            destination = st.text_input("Destination (Required)")
            travel_date = st.date_input("Travel Date")
            budget = st.number_input("Budget (INR)", min_value=0)
            
        notes = st.text_area("Notes / Requirements")
        
        # Submit Button
        submitted = st.form_submit_button("Save Enquiry")
        
        if submitted:
            if name and destination:
                try:
                    # 1. ALWAYS Create a New Lead (Even if name/phone exists)
                    new_lead = Lead(name=name, phone=phone, email=email)
                    db_session.add(new_lead)
                    db_session.commit()
                    
                    # 2. Create the Query linked to this new entry
                    new_query = Query(
                        lead_id=new_lead.id,
                        destination=destination,
                        status="New",
                        budget=budget,
                        notes=notes
                    )
                    db_session.add(new_query)
                    db_session.commit()
                    
                    st.success(f"✅ Enquiry for {name} saved successfully!")
                    
                except Exception as e:
                    st.error(f"Error: {e}")
            else:
                st.error("⚠️ Client Name and Destination are required.")
# --- PAGE 3: AI ITINERARY BUILDER (FINAL CLEAN VERSION) ---
elif menu == "AI Itinerary Builder":
    st.header("✨ Smart Itinerary Creator")
    
    if 'generated_itinerary' not in st.session_state:
        st.session_state['generated_itinerary'] = ""

    # API Check
    if not api_key:
        st.warning("⚠️ Enter API Key in Sidebar.")
        st.stop()

    # Select Client
    queries = db_session.query(Query).all()
    if not queries:
        st.info("No enquiries found.")
        st.stop()

    query_options = {f"{q.id}: {q.lead.name} ({q.destination})": q for q in queries}
    selected_query_label = st.selectbox("Select Client", list(query_options.keys()))
    
    if selected_query_label:
        selected_query = query_options[selected_query_label]
        
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
        if st.button("Generate Draft Itinerary"):
            with st.spinner("Writing Professional Itinerary..."):
                try:
                    # SMART MODEL SELECTOR (The Fix)
                    # This loops through available models and picks the first one that works
                    model_name = "gemini-pro" # Default backup
                    for m in genai.list_models():
                        if 'generateContent' in m.supported_generation_methods:
                            model_name = m.name
                            break # Found one! Stop looking.
                    
                    # Create the model using the found name
                    model = genai.GenerativeModel(model_name)
                    
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
                    
                    Example:
                    Day 1: 26 Feb - Arrival & Museum of the Future
                    (Description...)

                    Tone: Professional & Exciting.
                    """
                    response = model.generate_content(prompt)
                    st.session_state['generated_itinerary'] = response.text
                    st.success(f"Draft Created using {model_name}!")
                except Exception as e:
                    st.error(f"AI Error: {e}")

        # --- EDIT & FINALIZE (TEXT BOXES ONLY) ---
        if st.session_state['generated_itinerary']:
            st.markdown("---")
            
            # 1. ITINERARY
            st.subheader("1. Itinerary Content")
            final_text = st.text_area("Edit Itinerary:", 
                                    value=st.session_state['generated_itinerary'], 
                                    height=500,
                                    key="final_itinerary_box")
            
            col_a, col_b = st.columns(2)
            
            # 2. HOTELS (Text Box)
            with col_a:
                st.subheader("2. Accommodation")
                hotel_text = st.text_area("Enter Hotel Details:", 
                                        value="Option 1: Hilton Garden Inn (BB)\nOption 2: JW Marriott (BB)",
                                        height=200, 
                                        key="hotel_box")

            # 3. PRICE (Text Box)
            with col_b:
                st.subheader("3. Investment")
                price_text = st.text_area("Enter Final Price:", 
                                        value="Total Package Cost: INR 1,50,000 + Taxes\n\nIncludes:\n- Daily Breakfast\n- All Transfers\n- Visa Fees",
                                        height=200, 
                                        key="price_box")
            
            # 4. DOWNLOAD BUTTON
            if st.button("📄 Download Final PDF", type="primary"):
                pdf_data = create_itinerary_pdf(
                    selected_query.lead.name,
                    selected_query.destination,
                    final_text,
                    hotel_text,   # Uses the box above
                    price_text    # Uses the box above
                )
                
                st.download_button(
                    label="Click to Save PDF",
                    data=pdf_data,
                    file_name=f"Quote_{selected_query.lead.name}.pdf",
                    mime="application/pdf"
                )