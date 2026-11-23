"""SHOPPER launcher for Railway Railpack or local testing."""
import os
import uvicorn

def main():
    port = int(os.environ.get("PORT", "8000"))
    if not 1 <= port <= 65535:
        raise ValueError("Invalid PORT")
    uvicorn.run("main:app", host="0.0.0.0", port=port, workers=1)

if __name__ == "__main__":
    main()
