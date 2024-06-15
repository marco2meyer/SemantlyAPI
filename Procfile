release: ./setup.sh
web: gunicorn -w 2 -k uvicorn.workers.UvicornWorker --threads 2 app:app --bind 0.0.0.0:$PORT