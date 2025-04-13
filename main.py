from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
from pydantic import BaseModel
from supabase import create_client, Client
from typing import Optional, Dict, Any, List, Union
import openai
import uuid
import json

# Load environment variables
load_dotenv()

# Get environment variables with fallbacks
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Initialize FastAPI app first
app = FastAPI(
    title="Resume GPT API",
    description="API for generating tailored resumes based on job descriptions using OpenAI and Supabase.",
    version="1.2.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Supabase client only if credentials are available
supabase = None
if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Initialize OpenAI client if API key is available
if OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY

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

class GenericResponse(BaseModel):
    message: str
    data: Optional[Any] = None

class QueryParams(BaseModel):
    table: str
    select: str = "*"
    filters: Optional[Dict[str, Any]] = None
    limit: Optional[int] = None
    order: Optional[Dict[str, str]] = None

class InsertDataRequest(BaseModel):
    table: str
    data: Union[Dict[str, Any], List[Dict[str, Any]]]

class UpdateDataRequest(BaseModel):
    table: str
    data: Dict[str, Any]
    match_column: str
    match_value: Any

class DeleteDataRequest(BaseModel):
    table: str
    match_column: str
    match_value: Any

class ExecuteRawSQLRequest(BaseModel):
    query: str
    params: Optional[Dict[str, Any]] = None

class CreateTableRequest(BaseModel):
    table_name: str
    columns: Dict[str, str]
    primary_key: Optional[str] = None

class ResumeUploadRequest(BaseModel):
    user_id: Optional[str] = None
    content: str

class JobDescriptionUploadRequest(BaseModel):
    description: str

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
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase client not initialized. Check environment variables.")
    
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
    The tailored resume will be stored in the tailored_resumes table.
    """
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase client not initialized. Check environment variables.")
    if not openai.api_key:
        raise HTTPException(status_code=500, detail="OpenAI API key not configured. Check environment variables.")
    
    try:
        # Fetch base resume from Supabase
        resume_response = supabase.table("resumes").select("*").eq("user_id", request.user_id).execute()
        if not resume_response.data:
            raise HTTPException(status_code=400, detail="User not found")
        
        base_resume = resume_response.data[0]
        base_resume_id = base_resume["id"]
        base_resume_content = base_resume["content"]
        
        # Fetch job description from Supabase
        job_response = supabase.table("job_descriptions").select("*").eq("id", request.job_id).execute()
        if not job_response.data:
            raise HTTPException(status_code=400, detail="Job not found")
        
        job_description = job_response.data[0]["description"]
        
        # Generate tailored resume using OpenAI
        prompt = f"""
        Please tailor the following resume to match the job description.
        
        Base Resume:
        {base_resume_content}
        
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
        
        # Store the tailored resume in Supabase
        tailored_resume_data = {
            "user_id": request.user_id,
            "job_id": request.job_id,
            "base_resume_id": base_resume_id,
            "content": tailored_resume
        }
        
        supabase.table("tailored_resumes").insert(tailored_resume_data).execute()
        
        return TailorResumeResponse(
            user_id=request.user_id,
            job_id=request.job_id,
            tailored_resume=tailored_resume
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# New Database Gateway Endpoints for ChatGPT

@app.get("/tables", response_model=GenericResponse)
async def list_tables():
    """
    Lists all tables in the Supabase database.
    """
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase client not initialized. Check environment variables.")
    
    try:
        # This requires a raw SQL query since Supabase doesn't have a direct method to list tables
        result = supabase.rpc('get_tables').execute()
        
        return GenericResponse(
            message="Tables retrieved successfully",
            data=result.data
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/schema", response_model=GenericResponse)
async def get_schema():
    """
    Gets the database schema information including tables and their columns.
    """
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase client not initialized. Check environment variables.")
    
    try:
        result = supabase.rpc('get_schema_info').execute()
        
        return GenericResponse(
            message="Schema information retrieved successfully",
            data=result.data
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/query", response_model=GenericResponse)
async def query_data(params: QueryParams):
    """
    Queries data from a specified table with optional filters.
    """
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase client not initialized. Check environment variables.")
    
    try:
        query = supabase.table(params.table).select(params.select)
        
        # Apply filters if provided
        if params.filters:
            for column, value in params.filters.items():
                query = query.eq(column, value)
        
        # Apply order if provided
        if params.order:
            for column, direction in params.order.items():
                if direction.lower() == "asc":
                    query = query.order(column)
                else:
                    query = query.order(column, desc=True)
        
        # Apply limit if provided
        if params.limit:
            query = query.limit(params.limit)
        
        result = query.execute()
        
        return GenericResponse(
            message=f"Data retrieved from {params.table}",
            data=result.data
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/insert", response_model=GenericResponse)
async def insert_data(request: InsertDataRequest):
    """
    Inserts data into a specified table.
    """
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase client not initialized. Check environment variables.")
    
    try:
        result = supabase.table(request.table).insert(request.data).execute()
        
        return GenericResponse(
            message=f"Data inserted into {request.table}",
            data=result.data
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/update", response_model=GenericResponse)
async def update_data(request: UpdateDataRequest):
    """
    Updates data in a specified table based on a matching column value.
    """
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase client not initialized. Check environment variables.")
    
    try:
        result = supabase.table(request.table).update(request.data).eq(request.match_column, request.match_value).execute()
        
        return GenericResponse(
            message=f"Data updated in {request.table}",
            data=result.data
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/delete", response_model=GenericResponse)
async def delete_data(request: DeleteDataRequest):
    """
    Deletes data from a specified table based on a matching column value.
    """
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase client not initialized. Check environment variables.")
    
    try:
        result = supabase.table(request.table).delete().eq(request.match_column, request.match_value).execute()
        
        return GenericResponse(
            message=f"Data deleted from {request.table}",
            data=result.data
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/execute-sql", response_model=GenericResponse)
async def execute_raw_sql(request: ExecuteRawSQLRequest):
    """
    Executes a raw SQL query with optional parameters.
    """
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase client not initialized. Check environment variables.")
    
    try:
        # SECURITY WARNING: This endpoint could be dangerous if exposed publicly
        result = supabase.rpc('run_sql_query', {"sql_query": request.query, "params": request.params or {}}).execute()
        
        return GenericResponse(
            message="SQL query executed successfully",
            data=result.data
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/create-table", response_model=GenericResponse)
async def create_table(request: CreateTableRequest):
    """
    Creates a new table with the specified columns.
    """
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase client not initialized. Check environment variables.")
    
    try:
        # Build the CREATE TABLE SQL statement
        columns_sql = []
        for col_name, col_type in request.columns.items():
            columns_sql.append(f"{col_name} {col_type}")
        
        if request.primary_key:
            columns_sql.append(f"PRIMARY KEY ({request.primary_key})")
        
        columns_str = ", ".join(columns_sql)
        
        create_table_sql = f"CREATE TABLE {request.table_name} ({columns_str});"
        
        # Execute the SQL
        result = supabase.rpc('run_sql_query', {"sql_query": create_table_sql}).execute()
        
        return GenericResponse(
            message=f"Table {request.table_name} created successfully",
            data=result.data
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload-resume", response_model=GenericResponse)
async def upload_resume(request: ResumeUploadRequest):
    """
    Uploads a resume to the database.
    """
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase client not initialized. Check environment variables.")
    
    try:
        # Generate user_id if not provided
        user_id = request.user_id or str(uuid.uuid4())
        
        # Insert resume
        resume_data = {
            "user_id": user_id,
            "content": request.content
        }
        
        result = supabase.table("resumes").insert(resume_data).execute()
        
        return GenericResponse(
            message="Resume uploaded successfully",
            data={"user_id": user_id, "resume_id": result.data[0]["id"] if result.data else None}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload-job-description", response_model=GenericResponse)
async def upload_job_description(request: JobDescriptionUploadRequest):
    """
    Uploads a job description to the database.
    """
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase client not initialized. Check environment variables.")
    
    try:
        # Insert job description
        job_data = {
            "description": request.description
        }
        
        result = supabase.table("job_descriptions").insert(job_data).execute()
        
        return GenericResponse(
            message="Job description uploaded successfully",
            data={"job_id": result.data[0]["id"] if result.data else None}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
