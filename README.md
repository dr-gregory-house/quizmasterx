# QuizMaster X

A web-based quiz application built with Flask that supports multiple quiz modes including Marathon Mode.

## Features
- Multiple quiz modes
- User authentication
- Admin dashboard
- Marathon mode with timer
- Review system

## Prerequisites
- Python 3.11+
- Docker (for containerized deployment)

## Local Development Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd mcq_app
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. Initialize the database:
```bash
python run_migrations.py
```

6. Run the development server:
```bash
flask run
```

## Docker Deployment

1. Build the Docker image:
```bash
docker build -t mcq-app .
```

2. Run the container:
```bash
docker run -p 5000:5000 --env-file .env mcq-app
```

## Cloud Deployment (Google Cloud Run)

1. Set up Google Cloud SDK and authenticate:
```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

2. Deploy using Cloud Build:
```bash
gcloud builds submit --config cloudbuild.yaml
```

## Environment Variables

- `FLASK_APP`: Set to app.py
- `FLASK_ENV`: Set to production for deployment
- `SECRET_KEY`: Your secure secret key
- `DATABASE_URL`: Your database connection URL
- `DEBUG`: Set to False in production

## Security Notes

1. Always change the default SECRET_KEY in production
2. Enable HTTPS in production
3. Keep your dependencies updated
4. Never commit .env files
5. Use secure database credentials in production

## License

[Your License Here] 