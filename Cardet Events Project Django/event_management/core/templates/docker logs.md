🔍 View Logs from Docker Containers
✅ 1. Django App Logs
Your Django app is in the container named event_management.

To view the logs:

bash
Copy
Edit
docker logs event_management
This will show you the output from your Django runserver or gunicorn command — including errors, requests, and print() or logging.info() outputs.

⏱ You can also follow logs in real-time:

bash
Copy
Edit
docker logs -f event_management
✅ 2. Celery Logs
To see logs for your Celery worker:

bash
Copy
Edit
docker logs celery_worker
For Celery Beat scheduler:

bash
Copy
Edit
docker logs celery_beat
✅ 3. Flower Logs
bash
Copy
Edit
docker logs flower
Then visit your Flower UI at:

arduino
Copy
Edit
http://your_droplet_ip:5555
✅ 4. Database Logs (PostgreSQL)
bash
Copy
Edit
docker logs postgres_db
This is helpful if your Django app can't connect to the DB.

✅ 5. Redis Logs
bash
Copy
Edit
docker logs redis
✅ 6. PgAdmin Logs
bash
Copy
Edit
docker logs pgadmin
Then open your browser and go to:

arduino
Copy
Edit
http://your_droplet_ip:5050
✅ 7. All Logs Together (Optional)
If you want to monitor all logs together in real-time:

bash
Copy
Edit
docker-compose logs -f
Or, for just one service:

bash
Copy
Edit
docker-compose logs -f django # or celery, flower, etc.
🧠 Pro Tips
Use Ctrl+C to stop -f (follow) mode

If your logs are too long, you can tail the last 100 lines:

bash
Copy
Edit
docker logs --tail=100 event_management
You can also add timestamps:

bash
Copy
Edit
docker logs --timestamps event_management
Let me know if you'd like help analyzing any of those logs or setting up structured log output (e.g., logging to a file or sending logs to a service).
