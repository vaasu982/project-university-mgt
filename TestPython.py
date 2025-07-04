python-rest-upload/
├── app/
│   ├── main.py
│   └── upload_handler.py
├── requirements.txt
└── README.md
    
    fastapi==0.111.0
uvicorn==0.30.0
python-multipart==0.0.9
---
    from fastapi import FastAPI, UploadFile, File
from typing import List
from app.upload_handler import save_files

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Welcome to the Python 3.12 REST API"}

@app.post("/upload-files/")
async def upload_multiple_files(files: List[UploadFile] = File(...)):
    result = await save_files(files)
    return {"uploaded": result}
------------------------
# Optional: create a virtual env
python3.12 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the FastAPI app
uvicorn app.main:app --reload
