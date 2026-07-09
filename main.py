from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pathlib import Path
import uvicorn

app = FastAPI(title="Flappy Bird Clone Server")

# Define the path to the frontend HTML file
html_file = Path(__file__).parent / "index.html"

@app.get("/", response_class=HTMLResponse)
async def serve_game():
    """
    Serves the Flappy Bird game interface.
    """
    if not html_file.exists():
        return HTMLResponse(content="<h1>Error: index.html not found.</h1>", status_code=404)
    
    return html_file.read_text(encoding="utf-8")

if __name__ == "__main__":
    # Pass the app as an import string to enable reloading
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)