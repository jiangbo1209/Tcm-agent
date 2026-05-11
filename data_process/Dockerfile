FROM python:3.12-slim

WORKDIR /app

COPY pdf_upload/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY pdf_upload/ .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
