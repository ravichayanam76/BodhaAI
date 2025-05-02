import streamlit as st
import pdfplumber
import google.generativeai as genai
import tempfile
import re
import os
from PIL import Image
import base64

# 🔐 Gemini API key
genai.configure(api_key="AIzaSyBcjzeuyWVPUTKEYB8ftZr6dGUdKyEJeFc")  # Replace with your actual API Key

# 📘 Streamlit Config
st.set_page_config(page_title="Smart Exam Generator", layout="centered")

# === Background Setup ===
def get_base64_of_image(image_path):
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode()

image_path = "Bodha.png"  # Ensure image exists in the same folder
encoded_image = get_base64_of_image(image_path)


# Inject background CSS and content layout
st.markdown(f"""
<style>
html, body {{
    height: 100%;
    margin: 0;
}}

[data-testid="stAppViewContainer"] > .main {{
    background-image: url("data:image/png;base64,{encoded_image}");
    background-size: cover;
    background-position: center;
    background-repeat: no-repeat;
    background-attachment: fixed;
}}

.content-container {{
    display: flex;
    justify-content: center;
    padding-top: 80px;
    padding-bottom: 80px;
}}

.inner-box {{
    background: rgba(0, 0, 0, 0.65);
    padding: 40px;
    border-radius: 15px;
    max-width: 850px;
    width: 90%;
    color: white;
    box-shadow: 0 8px 24px rgba(0,0,0,0.5);
}}

.inner-box h1 {{
    text-align: center;
    font-size: 2.4em;
    font-weight: 800;
    margin-bottom: 30px;
    color: white;
    text-shadow: 2px 2px 4px rgba(0,0,0,0.6);
}}

label, .st-bx, .stSlider label, .stSelectbox label {{
    color: white !important;
}}

.stButton button {{
    background-color: #1f1f1f;
    color: white;
    border-radius: 8px;
    border: 1px solid white;
}}

.stButton button:hover {{
    background-color: white;
    color: black;
    transition: 0.3s ease-in-out;
}}
</style>

<div class="content-container">
<div class="inner-box">
<h1>BodhaAI – Generate. Evaluate. Elevate.</h1>
""", unsafe_allow_html=True)

# === UI ===
uploaded_file = st.file_uploader("Upload your textbook or PDF:", type=["pdf"])
question_type = st.selectbox("Select Question Type:", ["MCQ", "Fill in the blanks", "True/False", "Short Answer"])
difficulty = st.selectbox("Select Difficulty Level:", ["Easy", "Medium", "Hard"])
num_questions = st.slider("Number of Questions PER CHAPTER:", min_value=1, max_value=20, value=4)

# === Utility Functions ===
def clean_text(text):
    text = re.sub(r'\n+', '\n', text)
    text = re.sub(r'\s{2,}', ' ', text)
    return text.strip()

def extract_chapters_from_pdf(file_path):
    full_text = ""
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                full_text += page_text + "\n"
    full_text = clean_text(full_text)
    pattern = re.compile(r'(Chapter\s+(\d+))\b', re.IGNORECASE)
    matches = list(pattern.finditer(full_text))
    chapter_map = {}
    for i in range(len(matches)):
        chapter_num = int(matches[i].group(2))
        chapter_title = f"Chapter {chapter_num}"
        start = matches[i].start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
        content = full_text[start:end].strip()
        chapter_map[chapter_title] = content
    return dict(sorted(chapter_map.items(), key=lambda x: int(x[0].split()[-1]))), full_text

def generate_questions_with_gemini(text, difficulty, num_questions, q_type):
    if q_type == "MCQ":
        prompt = f"""
You are a question paper generator.

Given the following study material, generate {num_questions} {difficulty} level **MCQ questions** with **four options** each (A, B, C, D) and clearly indicate the **correct option** for each question.

---CONTENT START---
{text}
---CONTENT END---

Provide output in the following format (with spacing between lines):

Q1. <Question text>

A. Option A  
B. Option B  
C. Option C  
D. Option D  

Answer: <Correct Option Letter>

Q2. ...
"""
    else:
        prompt = f"""
You are a question paper generator.

From the following content, generate {num_questions} {difficulty} level questions of type "{q_type}".

---CONTENT START---
{text}
---CONTENT END---

Provide output in the following format (with spacing between lines):

Q1. <Question text>

Answer: <Answer>

Q2. ...
"""
    model = genai.GenerativeModel("models/gemini-1.5-flash-latest")
    response = model.generate_content(prompt)
    return response.text

# === Session State Init ===
if 'questions' not in st.session_state:
    st.session_state.questions = None
    st.session_state.answers = None
    st.session_state.chapters = {}
    st.session_state.full_text = ""
    st.session_state.selected_chapters = []

# === PDF Processing ===
if uploaded_file is not None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        tmp_file.write(uploaded_file.read())
        pdf_path = tmp_file.name

    st.success("✅ PDF uploaded successfully!")

    if not st.session_state.chapters:
        with st.spinner("📖 Extracting chapters..."):
            chapters, full_text = extract_chapters_from_pdf(pdf_path)
            st.session_state.chapters = chapters
            st.session_state.full_text = full_text

    chapter_options = list(st.session_state.chapters.keys())
    selected_chapters = st.multiselect(
        "Select Chapters to Generate Questions From (or leave empty to use full content):",
        chapter_options,
        default=st.session_state.selected_chapters
    )
    st.session_state.selected_chapters = selected_chapters

    if st.button("Generate Questions"):
        if selected_chapters:
            selected_text = "\n\n".join([st.session_state.chapters[ch] for ch in selected_chapters])
            total_questions = num_questions * len(selected_chapters)
        else:
            selected_text = st.session_state.full_text
            total_questions = num_questions

        try:
            combined_output = generate_questions_with_gemini(selected_text, difficulty, total_questions, question_type)
        except Exception as e:
            st.error(f"⚠️ Gemini failed: {e}")
            combined_output = ""

        question_lines = []
        answer_lines = []
        buffer = []
        answer_count = 1

        for line in combined_output.splitlines():
            if line.strip().lower().startswith("answer:"):
                answer_text = line.strip().split("Answer:", 1)[-1].strip()
                answer_lines.append(f"Answer {answer_count}: {answer_text}")
                answer_count += 1
                buffer.append("")
                question_lines.append("")
            elif line.strip():
                buffer.append(line.strip())
                if question_type == "MCQ" and re.match(r'^[A-Da-d][\.\)]', line.strip()):
                    buffer.append("")
            else:
                buffer.append("")

        question_lines = [line for line in buffer if not line.strip().lower().startswith("answer")]
        st.session_state.questions = "\n".join(question_lines)
        st.session_state.answers = "\n".join(answer_lines)

# === Output Display ===
if st.session_state.questions:
    st.success("✅ Question Paper Generated Successfully")
    st.text_area("📄 View the Question Paper", st.session_state.questions, height=500)
    st.download_button("📥 Download Question Paper", st.session_state.questions.encode("utf-8"), "Question_Paper.txt")

if st.session_state.answers:
    st.download_button("📥 Download Answer Key", st.session_state.answers.encode("utf-8"), "Answer_Key.txt")

# === Close content block ===
st.markdown("</div></div>", unsafe_allow_html=True)
