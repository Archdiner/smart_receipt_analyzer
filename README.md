# Smart Spend Tracker

A comprehensive finance and spending tracker that automates data extraction from receipts and transaction messages, categorizes your spending, and provides insightful visualizations. Built with a FastAPI backend, AWS Textract (or local OCR), and a Streamlit frontend MVP.

## Features

- **Receipt & SMS Upload**  
  Upload receipt images or SMS screenshots via REST API.
- **OCR & Parsing**  
  Extract vendor name, date, total amount (and items if available) using AWS Textract or a local OCR engine.
- **AI-Powered Categorization**  
  Assign each transaction to one of 15 predefined spending sectors via a language model.
- **Interactive Dashboard**  
  Streamlit-based UI with:
  - Spending charts by sector and over time
  - Transaction history table with filters and export options
  - Manual expense entry form
- **User Management & Authentication**  
  Secure sign-up and login (email/password and OAuth providers).
- **Data Persistence**  
  PostgreSQL (self-hosted or via Supabase) to store users, transactions, and raw OCR data.
- **Containerized & Deployable**  
  Docker setup for consistent local development and cloud deployment.

## Tech Stack

| Layer                   | Technology                                  |
|-------------------------|---------------------------------------------|
| Backend                 | FastAPI, Uvicorn, Python                    |
| OCR                     | PaddleOCR       |
| AI Categorization       | OpenAI GPT-4o-mini
| Authentication & Database | Supabase (PostgreSQL, Auth, Storage)      |
| Frontend (MVP)          | Streamlit                                   |
| Containerization        | Docker, Docker Compose                      |
| Deployment              | AWS (ECS/Fargate), GCP (Cloud Run), Heroku  |

## Installation & Setup

### Prerequisites

- Docker and Docker Compose
- AWS account (for Textract and S3) or local OCR alternative
- Supabase project (optional) for authentication and database

### Clone and Configure

```bash
git clone https://github.com/your-username/smart-spend-tracker.git
cd smart-spend-tracker
```

1. **Environment Variables**: Copy `.env.example` to `.env` and set your credentials:
   ```dotenv
   FASTAPI_HOST=0.0.0.0
   FASTAPI_PORT=8000
   AWS_ACCESS_KEY_ID=...
   AWS_SECRET_ACCESS_KEY=...
   TEXTRACT_REGION=...
   DATABASE_URL=postgresql://user:pass@host:5432/dbname
   SUPABASE_URL=https://xyz.supabase.co
   SUPABASE_KEY=...
   OPENAI_API_KEY=...
   ```

## Usage

1. **Register / Login**: Create an account or sign in.
2. **Dashboard**: View spending charts, recent transactions, and add manual entries.
3. **Upload Receipts / SMS**: Navigate to the upload page, select an image, analyze, and save.
4. **History & Export**: Filter transactions by date or sector and download CSV reports.

## Roadmap

- **Phase 1 (MVP)**: Core upload and parsing, basic Streamlit dashboard.
- **Phase 2**: React or Next.js frontend, background processing, budget alerts.
- **Phase 3**: Native mobile app with offline support and camera integration.
- **Phase 4**: Advanced analytics (forecasting, trends) and multi-user plans.

## Contributing

Contributions, issues, and feature requests are welcome. Feel free to fork and submit a pull request.

**Happy Tracking!**

