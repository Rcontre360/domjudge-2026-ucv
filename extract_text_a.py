from pypdf import PdfReader
reader = PdfReader("problems.pdf")
page = reader.pages[3] # Problem A is on page 3 (index 3 based on process_problems.py)
print(page.extract_text())
