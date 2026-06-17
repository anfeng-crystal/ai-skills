from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse
import uvicorn
from utils import read_docx, read_xlsx

app = FastAPI(title="Document Reader MCP", version="0.1.0")

@app.post("/read")
async def read_document(file: UploadFile = File(...)):
    content = await file.read()
    suffix = file.filename.lower().split('.')[-1]
    if suffix == "docx":
        try:
            txt = read_docx(content)
            return PlainTextResponse(txt, media_type="text/plain")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"docx parse error: {e}")
    elif suffix == "xlsx":
        try:
            data = read_xlsx(content)
            return JSONResponse(data)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"xlsx parse error: {e}")
    else:
        raise HTTPException(status_code=415, detail="Only .docx and .xlsx are supported")

@app.get("/healthz")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
