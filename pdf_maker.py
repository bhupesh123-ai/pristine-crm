from fpdf import FPDF

class PDF(FPDF):
    def header(self):
        # 1. LOGO
        try:
            self.image('logo.png', 10, 8, 30) 
        except:
            pass 

        # 2. BRANDING STRIP
        self.set_fill_color(0, 102, 102) # Teal
        self.rect(0, 0, 210, 5, 'F') 

        # 3. COMPANY NAME
        self.set_font('Arial', 'B', 12)
        self.set_text_color(0, 102, 102)
        self.cell(0, 10, 'PRISTINE VACATIONS', 0, 1, 'R')
        self.set_font('Arial', '', 8)
        self.set_text_color(100, 100, 100)
        self.cell(0, 5, 'Making Holidays Memorable', 0, 1, 'R')
        self.ln(10)

    def footer(self):
        self.set_y(-25)
        self.set_draw_color(200, 200, 200)
        self.line(10, 272, 200, 272)
        
        self.set_font('Arial', 'B', 9)
        self.set_text_color(0, 0, 0)
        self.cell(0, 5, 'PRISTINE VACATIONS', 0, 1, 'C')
        
        self.set_font('Arial', '', 8)
        self.set_text_color(50, 50, 50)
        self.cell(0, 5, 'College Road, Ludhiana 141001, Phone: 0161-4623384', 0, 1, 'C')
        self.cell(0, 5, 'Email - info@pristine.in', 0, 1, 'C')
        self.cell(0, 5, f'Page {self.page_no()}', 0, 0, 'R')

def create_itinerary_pdf(client_name, destination, itinerary_text, hotel_details, price_text):
    pdf = PDF()
    pdf.set_auto_page_break(auto=True, margin=30)
    pdf.add_page()
    
    def clean(text):
        return text.replace('₹', 'Rs.').replace('’', "'").replace('–', "-").encode('latin-1', 'replace').decode('latin-1')

    # 1. TITLE
    pdf.set_font("Arial", "B", 20)
    pdf.set_text_color(0, 102, 102)
    pdf.cell(0, 10, "Travel Proposal", 0, 1, 'L')
    
    pdf.set_font("Arial", "", 12)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 8, f"Prepared for: {clean(client_name)}", 0, 1, 'L')
    pdf.cell(0, 8, f"Destination: {clean(destination)}", 0, 1, 'L')
    pdf.ln(5)
    
    # 2. ITINERARY
    lines = itinerary_text.split('\n')
    for line in lines:
        line = clean(line.strip())
        if not line: continue
        
        if line.startswith("Day") or line.startswith("**Day"):
            pdf.ln(5)
            pdf.set_fill_color(0, 102, 102)
            pdf.set_text_color(255, 255, 255)
            pdf.set_font("Arial", "B", 11)
            pdf.cell(0, 8, f"  {line.replace('*', '')}", 0, 1, 'L', 1)
            pdf.ln(2)
        else:
            pdf.set_text_color(50, 50, 50)
            pdf.set_font("Arial", "", 10)
            pdf.multi_cell(0, 5, line)
            
    # 3. ACCOMMODATION
    if hotel_details:
        pdf.add_page()
        pdf.set_font("Arial", "B", 14)
        pdf.set_text_color(0, 102, 102)
        pdf.cell(0, 10, "Accommodation Details", 0, 1)
        
        pdf.set_font("Arial", "", 10)
        pdf.set_text_color(0, 0, 0)
        pdf.set_fill_color(245, 245, 245)
        pdf.multi_cell(0, 6, clean(hotel_details), 1, 'L', True)
        pdf.ln(10)

    # 4. INVESTMENT
    pdf.set_font("Arial", "B", 14)
    pdf.set_text_color(0, 102, 102)
    pdf.cell(0, 10, "Investment & Inclusions", 0, 1)
    
    pdf.set_font("Arial", "", 10)
    pdf.set_text_color(0, 0, 0)
    pdf.set_fill_color(255, 252, 240)
    pdf.multi_cell(0, 6, clean(price_text), 1, 'L', True)
    
    # 5. TERMS & CONDITIONS (Restored Full List)
    pdf.ln(15)
    pdf.set_font("Arial", "B", 10)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 8, "Terms & Conditions:", 0, 1)
    
    pdf.set_font("Arial", "", 9)
    pdf.set_text_color(50, 50, 50)
    terms = """1. All rates are subject to TCS and GST as per government regulations.
2. Rates are subject to change as per availability.
3. No booking is confirmed until the advance payment is received.
4. Passports must be valid for at least 6 months from the date of return.
5. Final payment is subject to ROE (Rate of Exchange) fluctuations.
6. Standard Hotel Check-in: 14:00 | Check-out: 11:00.
7. Visa issuance is at the sole discretion of the Embassy."""
    
    pdf.multi_cell(0, 5, terms)
    
    return pdf.output(dest='S').encode('latin-1')