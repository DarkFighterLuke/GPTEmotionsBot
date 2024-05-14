import os

import telebot
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
bot = telebot.TeleBot(token=os.getenv("BOT_TOKEN"))
client = OpenAI(api_key=os.getenv("OPENAI_TOKEN"))


@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Benvenuto nel bot di GPTEmotions!\nScrivi una frase da analizzare per ottenere l'emozione "
                          "rilevata :)")


def gpt_chat(user_input : str):
    completion = client.chat.completions.create(
        model="ft:gpt-3.5-turbo-0125:personal:emotions:9MFmXPJ9",
        messages=[
            {"role": "system", "content": "Sei un chatbot che riconosce quale emozione tra 'gioia', 'vergogna', "
                                          "'colpevolezza', 'paura', 'rabbia', 'tristezza' esprime la frase che gli "
                                          "viene posta. Se non conosci la risposta rispondi con 'idk'."},
            {"role": "user", "content": user_input}
        ]
    )
    return completion.choices[0].message.content


def parse_query(message_text):
    return "".join(message_text.split()[1:])


@bot.message_handler(func=lambda message: message.text[0] != "/")
def analyze_sentiment(message):
    sentiment = gpt_chat(message.text)
    bot.reply_to(message, sentiment)


@bot.message_handler(commands=["analyze"])
def analyze_sentiment_by_command(message):
    text = parse_query(message.text)
    sentiment = gpt_chat(text)
    bot.reply_to(message, sentiment)


bot.infinity_polling()
