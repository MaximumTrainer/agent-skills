FROM python:3.12

WORKDIR /app

COPY . .

RUN pip install -r requirements.txt

ENV DATABASE_PASSWORD=hunter2
ENV PORT=8000

EXPOSE 8000

CMD python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
