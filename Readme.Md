# README.md

# AI Lead Generation Backend

## Project Overview

This project is a **FastAPI backend** designed to simulate a real-world AI lead-generation and outreach workflow. It connects to **Google Gemini (Generative AI)**, rotates API keys automatically, and integrates seamlessly with **n8n** for automation.

The backend supports:

- Prompt generation using Google Gemini API  
- Automatic rotation of multiple API keys to handle rate limits  
- Email alerts when certain keys reach their usage limits  
- Integration with n8n for sending AI-generated messages, saving results to Supabase, and triggering personalized AI voice calls

> ⚠️ Note: React or any frontend framework has **not** been used in this project. Using React would have added unnecessary complexity for this backend-focused simulation. The main goal was to demonstrate **API design, automation, and AI integration**.

---

## Features Implemented

### FastAPI Backend

- `/generate` endpoint for AI prompt generation  
- Handles **key rotation** automatically when rate limits are reached  
- Sends **email alerts** using Nodemailer when specific API keys reach their limit  
- Returns AI-generated responses in JSON for consumption by n8n or other clients

### n8n Automation Workflow

- Accepts prospect information via Webhook  
- Calls the FastAPI backend with dynamic prompts  
- Saves responses and metadata to **Supabase**  
- Formats and sends emails with generated messages  
- Logs API calls and workflow statuses

### AI Voice Integration (Retell AI)

- Supports personalized AI voice calls  
- Can analyze call results and determine next steps based on responses

---

## Setup Instructions

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd <repo-directory>
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Create a `.env` file:

```env
GOOGLE_GEMINI_API_KEYS=key1,key2,key3,key4,key5,key6,key7,key8,key9,key10
EMAIL_HOST=smtp.example.com
EMAIL_PORT=587
EMAIL_USER=your-email@example.com
EMAIL_PASSWORD=your-email-password
ALERT_EMAIL=alert-recipient@example.com
```

### 4. Run the FastAPI server

```bash
uvicorn main:app --reload
```

- Endpoint: `POST /generate`  
- Test via **Postman** or **n8n webhook**  
- Example JSON body:

```json
{
  "prompt": "Write a 4-step LinkedIn cold outreach for a SaaS founder.",
  "email_to": "youremail@example.com",
  "metadata": {
    "firstName": "John",
    "lastName": "Doe",
    "companyName": "Acme Inc",
    "LinkedInURL": "https://linkedin.com/in/johndoe",
    "website": "https://acme.com",
    "phoneNumber": "+1234567890"
  }
}
```

---

## Notes

- React frontend was deliberately **not included** to keep the focus on **backend, API, and automation layers**.  
- All AI interactions are handled server-side or via n8n automation workflows.  
- This project is fully functional for **demo purposes** and can be extended with a frontend later if needed.

---

## Future Improvements

- Add a **React or Streamlit frontend** for interactive testing  
- Extend key rotation logic to support **dynamic key provisioning**  
- Add more detailed logging and metrics for API usage

---

## Contact


For questions or support, contact **Sudesh Patil/ Sudeshrpatil20121@gmail.com**.
