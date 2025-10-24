import streamlit as st
import requests
import json


FASTAPI_URL = "http://127.0.0.1:8000/generate"  
N8N_WEBHOOK_URL = "https://your-n8n-instance.com/webhook/generate-prospect"  


st.title("Sendora AI Prompt Generator")

st.markdown("""
Enter the details for AI generation. This can be used standalone or integrated with n8n workflow.
""")


prompt = st.text_area("Enter AI Prompt", "Write a 4-step LinkedIn cold outreach for a SaaS founder.")


st.subheader("Prospect Metadata")
first_name = st.text_input("First Name", "")
last_name = st.text_input("Last Name", "")
company_name = st.text_input("Company Name", "")
linkedin_url = st.text_input("LinkedIn URL", "")
website = st.text_input("Website", "")
phone_number = st.text_input("Phone Number", "")


email_to = st.text_input("Alert Email (for key usage)", "")

metadata = {
    "firstName": first_name,
    "lastName": last_name,
    "companyName": company_name,
    "LinkedInURL": linkedin_url,
    "website": website,
    "phoneNumber": phone_number
}

if st.button("Generate AI Response"):
    if not prompt:
        st.error("Please enter a prompt!")
    else:
        payload = {
            "prompt": prompt,
            "email_to": email_to,
            "metadata": metadata
        }

        with st.spinner("Calling AI server..."):
            try:
                response = requests.post(FASTAPI_URL, json=payload, timeout=60)
                response.raise_for_status()
                data = response.json()
                

                st.success("AI Response Generated Successfully!")
                st.json(data)

                # this will Send to n8n webhook
                if N8N_WEBHOOK_URL:
                    try:
                        n8n_payload = {**metadata, "aiResponse": data.get("raw_response", "")}
                        n8n_resp = requests.post(N8N_WEBHOOK_URL, json=n8n_payload, timeout=30)
                        if n8n_resp.status_code == 200:
                            st.info("Sent AI response to n8n successfully!")
                        else:
                            st.warning(f"n8n webhook returned status {n8n_resp.status_code}")
                    except Exception as e:
                        st.error(f"Failed to send data to n8n: {e}")

            except requests.exceptions.RequestException as e:
                st.error(f"Error calling AI server: {e}")
