FROM python:3.12
LABEL authors="DarkFighterLuke"

RUN pip install openai pyTelegramBotAPI python-dotenv
ADD main.py .
ADD .env .
ENTRYPOINT ["python", "main.py"]