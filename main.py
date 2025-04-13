from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
from pydantic import BaseModel
from supabase import create_client, Client
from typing import Optional
import openai
import uuid

# Load environment variables
load_dotenv()

# Get environment variables with fallbacks
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Validate required environment variables
if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Missing required environment variables: SUPABASE_URL and SUPABASE_KEY must be set")

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Initialize OpenAI client
if OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY

app = FastAPI(
    title="Resume GPT API",
    description="API for generating tailored resumes based on job descriptions using OpenAI and Supabase.",
    version="1.1.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TailorResumeRequest(BaseModel):
    user_id: str
    job_id: int

class TailorResumeResponse(BaseModel):
    user_id: str
    job_id: int
    tailored_resume: str

class SampleDataResponse(BaseModel):
    message: str
    user_id: str
    job_id: int

@app.get("/")
async def root():
    return {"message": "Welcome to Resume GPT API"}

@app.post(
    "/insert-sample-data",
    response_model=SampleDataResponse,
    responses={
        200: {
            "description": "Successfully inserted sample data",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Sample data inserted successfully",
                        "user_id": "123e4567-e89b-12d3-a456-426614174000",
                        "job_id": 1
                    }
                }
            }
        },
        500: {
            "description": "Failed to insert sample data due to a server error"
        }
    }
)
async def insert_sample_data():
    """
    Inserts a randomly generated user with a sample resume and job description into the database.
    Returns the `user_id` and `job_id` to use for testing the resume tailoring endpoint.
    """
    try:
        # Generate a sample user_id
        user_id = str(uuid.uuid4())
        
        # Sample base resume
        base_resume = """
        John Doe
        Software Engineer
        
        Experience:
        - Senior Software Engineer at Tech Corp (2020-Present)
          * Led development of microservices architecture
          * Implemented CI/CD pipelines
          * Mentored junior developers
        
        - Software Engineer at Startup Inc (2018-2020)
          * Developed RESTful APIs
          * Worked with React and Node.js
          * Implemented automated testing
        
        Skills:
        - Python, JavaScript, React, Node.js
        - AWS, Docker, Kubernetes
        - Agile methodologies
        """
        
        # Sample job description
        job_description = """
        Senior Full Stack Developer
        
        We are looking for a Senior Full Stack Developer to join our team. The ideal candidate will have:
        
        Requirements:
        - 5+ years of experience in software development
        - Strong experience with React and Node.js
        - Experience with microservices architecture
        - Knowledge of AWS and cloud technologies
        - Experience with CI/CD pipelines
        - Strong problem-solving skills
        
        Responsibilities:
        - Develop and maintain web applications
        - Design and implement microservices
        - Work with cloud technologies
        - Mentor junior developers
        - Implement CI/CD pipelines
        """
        
        # Insert base resume
        resume_data = {
            "user_id": user_id,
            "content": base_resume
        }
        supabase.table("resumes").insert(resume_data).execute()
        
        # Insert job description
        job_data = {
            "description": job_description
        }
        job_response = supabase.table("job_descriptions").insert(job_data).execute()
        job_id = job_response.data[0]["id"]
        
        return SampleDataResponse(
            message="Sample data inserted successfully",
            user_id=user_id,
            job_id=job_id
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post(
    "/tailor-resume",
    response_model=TailorResumeResponse,
    responses={
        200: {
            "description": "Successfully generated a tailored resume",
            "content": {
                "application/json": {
                    "example": {
                        "user_id": "123e4567-e89b-12d3-a456-426614174000",
                        "job_id": 1,
                        "tailored_resume": "Tailored resume content..."
                    }
                }
            }
        },
        400: {
            "description": "Invalid user or job ID"
        },
        500: {
            "description": "Server error or issue with OpenAI API"
        }
    }
)
async def tailor_resume(request: TailorResumeRequest):
    """
    Tailors a user's base resume to a specific job description using GPT.
    You must provide a valid `user_id` and `job_id` that exist in the Supabase database.
    """
    try:
        # Fetch base resume from Supabase
        resume_response = supabase.table("resumes").select("*").eq("user_id", request.user_id).execute()
        if not resume_response.data:
            raise HTTPException(status_code=400, detail="User not found")
        
        base_resume = resume_response.data[0]["content"]
        
        # Fetch job description from Supabase
        job_response = supabase.table("job_descriptions").select("*").eq("id", request.job_id).execute()
        if not job_response.data:
            raise HTTPException(status_code=400, detail="Job not found")
        
        job_description = job_response.data[0]["description"]
        
        # Generate tailored resume using OpenAI
        prompt = f"""
        Please tailor the following resume to match the job description.
        
        Base Resume:
        {base_resume}
        
        Job Description:
        {job_description}
        
        Please provide a tailored version of the resume that highlights relevant skills and experiences.
        """
        
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a professional resume writer."},
                {"role": "user", "content": prompt}
            ]
        )
        
        tailored_resume = response.choices[0].message.content
        
        return TailorResumeResponse(
            user_id=request.user_id,
            job_id=request.job_id,
            tailored_resume=tailored_resume
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
