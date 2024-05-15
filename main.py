import json
import logging
import os

import telebot
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
bot = telebot.TeleBot(token=os.getenv("BOT_TOKEN"))
client = OpenAI(api_key=os.getenv("OPENAI_TOKEN"))
logger = logging.getLogger("[GPTEmotionsBot]")
logging.basicConfig(level=logging.INFO)

accuracy_threshold = 0.3
answer_format = """
{
   "sentiments": [
      {
         "sentiment": "emozione1",
         "accuracy": accuratezza1
      },
      {
         "sentiment": "emozione2",
         "accuracy": accuratezza2
      },
      {
         "sentiment": "emozione3",
         "accuracy": accuratezza3
      }
   ]
}
"""


@bot.message_handler(commands=['start'])
def send_welcome(message):
    logger.info(f"User {message.from_user.username} sent /start command")
    bot.reply_to(message, "Benvenuto nel bot di GPTEmotions!\nScrivi una frase da analizzare per ottenere l'emozione "
                          "rilevata :)")


def gpt_chat(user_input: str):
    completion = client.chat.completions.create(
        model="ft:gpt-3.5-turbo-0125:personal:emotions:9MFmXPJ9",
        messages=[
            {"role": "system", "content": f"Sei un chatbot che riconosce le tre emozioni più probabili tra 'gioia', 'vergogna', 'colpevolezza', 'paura', 'rabbia', 'tristezza' esprime la frase che gli viene posta. Se non conosci la risposta rispondi con 'idk'. Fornisci risposte in formato json con la seguente struttura '{answer_format}', dove accuratezza è la confidence con cui hai previsto per la specifica emozione."},
            {"role": "user", "content": user_input}
        ]
    )
    return completion.choices[0].message.content


def parse_answer_sentiments(answer_json):
    answer = json.loads(answer_json)
    return sorted(answer.get('sentiments', []), key=lambda x: x['accuracy'], reverse=True)


def parse_query(message_text):
    text = message_text.split()[1:]
    return "".join(t + " " for t in text)


def create_formatted_message(sentiments):
    sentiments = [s for s in sentiments if s.get('accuracy', 0) >= accuracy_threshold]
    if len(sentiments) == 0:
        reply = "Non sono riuscito ad individuare quali emozioni contiene questa frase..."
    else:
        reply = "Ho riconosciuto le seguenti emozioni:\n"
        for sentiment in sentiments:
            reply += f"`{sentiment.get('sentiment')}` con un'accuratezza del `{round(sentiment.get('accuracy'), 4) * 100}%`\n"

    return reply


@bot.message_handler(func=lambda message: message.text[0] != "/")
def analyze_sentiment(message):
    logger.info(f"User {message.from_user.username} sent text: {message.text}")
    sentiments = parse_answer_sentiments(gpt_chat(message.text))

    bot.reply_to(message, create_formatted_message(sentiments), parse_mode="markdown")


@bot.message_handler(commands=["analyze"])
def analyze_sentiment_by_command(message):
    text = parse_query(message.text)
    logger.info(f"User {message.from_user.username} sent /analyze command with text '{text}'")
    sentiments = parse_answer_sentiments(gpt_chat(text))

    bot.reply_to(message, create_formatted_message(sentiments), parse_mode="markdown")


bot.infinity_polling()
