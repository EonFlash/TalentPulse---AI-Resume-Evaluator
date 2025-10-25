import streamlit as st
import time

st.set_page_config(page_title="Talent Pulse - Evaluate your resume", layout="wide")
st.title(":blue[_Talent Pulse_] - Evaluate your resume")
st.divider()

st.info("UPLOAD THE CANDIDATE RESUME",icon="🔹")
with st.form("Upload form"):
    
    uploaded = st.file_uploader("Upload a PDF or DOC/DOCX file")
    submitted = st.form_submit_button("Evaluate Resume")

    if submitted:
        if uploaded is None:
            st.warning("Please upload a resume first.")
        else:
            # placeholders we can update
            status = st.empty()       # will show dynamic status text
            progress = st.progress(0) # progress bar

            # single spinner for the whole operation
            with st.spinner("Processing..."):
                # Stage 1
                status.markdown("⏳ **Extracting info...**")
                time.sleep(1.2)
                progress.progress(20)

                # Stage 2
                status.markdown("🔍 **Parsing sections & scoring...**")
                time.sleep(1.5)
                progress.progress(55)

                # Stage 3
                status.markdown("⚙️ **Applying scoring rules & finalizing**")
                time.sleep(1.5)
                progress.progress(90)

                # Finalize
                status.markdown("✅ **Finalizing results**")
                time.sleep(0.8)
                progress.progress(100)

            time.sleep(0.5)
            progress.empty()
            # Replace status with final success
            status.success("✅ Resume evaluated successfully!")
