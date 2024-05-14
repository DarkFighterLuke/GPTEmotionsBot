FROM python:3.12
LABEL authors="DarkFighterLuke"

ADD main.py .
ADD .env .
RUN pip install openai pyTelegramBotAPI python-dotenv
ENTRYPOINT ["python", "main.py"]