import csv
import json
import logging
import os

import telebot
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
bot = telebot.TeleBot(token=os.getenv("BOT_TOKEN"))
client = OpenAI(api_key=os.getenv("OPENAI_TOKEN"))
logger = logging.getLogger("[GPTEmotionsBot]")
logging.basicConfig(level=logging.INFO)

supervision_file_path = "output/supervision.csv"
accuracy_threshold = 0.5
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

conversation_state = {}
conversation_last_message = {}
conversation_last_sentiments = {}


@bot.message_handler(commands=['start'])
def send_welcome(message):
    logger.info(f"User {message.from_user.username} sent /start command")
    bot.reply_to(message, "Benvenuto nel bot di GPTEmotions!\nScrivi una frase da analizzare per ottenere l'emozione "
                          "rilevata :)")


def gpt_chat(user_input: str):
    completion = client.chat.completions.create(
        model="ft:gpt-3.5-turbo-0125:personal:emotions:9MFmXPJ9",
        messages=[
            {"role": "system", "content": f"Sei un chatbot che riconosce le tre emozioni più probabili tra 'gioia', "
                                          f"'vergogna', 'colpevolezza', 'paura', 'rabbia', 'tristezza' esprime la "
                                          f"frase che gli viene posta. Se non conosci la risposta rispondi con 'idk'. "
                                          f"Fornisci risposte in formato json con la seguente struttura '"
                                          f"{answer_format}', dove accuratezza è la confidence con cui hai previsto "
                                          f"per la specifica emozione."},
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


def to_comma_separated_sentiments(sentiments_json):
    sentiments_str = ""
    for sentiment in sentiments_json:
        sentiments_str += sentiment.get("sentiment") + ", "
    return sentiments_str[:-2]


def filter_sentiments_by_threshold(sentiments):
    return [s for s in sentiments if s.get('accuracy', 0) >= accuracy_threshold]


def create_formatted_message(chat_id, sentiments, supervised=True):
    sentiments = filter_sentiments_by_threshold(sentiments)
    if len(sentiments) == 0:
        reply = "Non sono riuscito ad individuare quali emozioni contiene questa frase...\n"
        if supervised:
            reply += "Ti andrebbe di aiutarmi a capire quali emozioni conteneva la frase?"
            conversation_state[chat_id] = "yes_no_answer_no_res"
    else:
        reply = "Ho riconosciuto le seguenti emozioni:\n"
        for sentiment in sentiments:
            reply += f"`{sentiment.get('sentiment')}` con un'accuratezza del `{round(sentiment.get('accuracy'), 4) * 100}%`\n"
        if supervised:
            reply += "Le emozioni riconosciute sono corrette?"
            conversation_state[chat_id] = "yes_no_answer"

    return reply


def add_to_supervision_file(timestamp, user_id, username, name, chat_id, text, predicted_sentiments, sentiments):
    headers = ["datetime", "user_id", "username", "name", "chat_id", "text", "predicted_sentiments", "real_sentiments"]
    if not os.path.isfile(supervision_file_path):
        os.makedirs(os.path.dirname(supervision_file_path), exist_ok=True)
        with open(supervision_file_path, "w") as f:
            writer = csv.writer(f, delimiter='|', lineterminator='\n')
            writer.writerow(headers)
    with open(supervision_file_path, "a") as f:
        writer = csv.writer(f, delimiter='|', lineterminator='\n')
        writer.writerow([datetime.fromtimestamp(timestamp), user_id, username, name, chat_id, text,
                         predicted_sentiments, sentiments])


@bot.message_handler(func=lambda message: conversation_state.get(message.chat.id, "") == "yes_no_answer_no_res" and not message.text.startswith("/"))
def handle_yes_no_answer_no_res(message):
    if "no" in message.text.lower():
        conversation_state[message.chat.id] = "no_answer_no_res"
        reply = "Come non detto allora! Inviami pure la prossima frase"
    elif "sì" in message.text.lower() or "si" in message.text.lower():
        conversation_state[message.chat.id] = "yes_answer_no_res"
        reply = "Indicami le emozioni che conteneva la frase separate da una virgola"
    else:
        conversation_state[message.chat.id] = "no_answer_no_res"
        reply = "Lo prendo come un no. Grazie lo stesso :)"

    bot.reply_to(message, reply)


@bot.message_handler(func=lambda message: conversation_state.get(message.chat.id, "") == "yes_answer_no_res" and not message.text.startswith("/"))
def handle_yes_answer_no_res(message):
    add_to_supervision_file(message.date, message.from_user.id, message.from_user.username,
                            f"{message.from_user.first_name} {message.from_user.last_name}",
                            message.chat.id, conversation_last_message[message.chat.id], "", message.text)
    conversation_state[message.chat.id] = ""

    bot.reply_to(message, "Grazie per il tuo contributo!")


@bot.message_handler(func=lambda message: conversation_state.get(message.chat.id, "") == "yes_no_answer" and not message.text.startswith("/"))
def handle_yes_no_answer(message):
    if "sì" in message.text.lower() or "si" in message.text.lower():
        add_to_supervision_file(message.date, message.from_user.id, message.from_user.username,
                                f"{message.from_user.first_name} {message.from_user.last_name}",
                                message.chat.id, conversation_last_message[message.chat.id],
                                conversation_last_sentiments.get(message.chat.id),
                                to_comma_separated_sentiments(
                                    filter_sentiments_by_threshold(conversation_last_sentiments.get(message.chat.id))))
        conversation_state[message.chat.id] = ""
        bot.reply_to(message, "Grandioso! Grazie per il tuo contributo")
    else:
        reply = ""
        if "no" not in message.text.lower():
            reply += "Lo prendo come un no.\n"
        reply += "Allora per favore indicami le emozioni che conteneva la frase separate da una virgola"
        bot.reply_to(message, reply)
        conversation_state[message.chat.id] = "no_answer"


@bot.message_handler(func=lambda message: conversation_state.get(message.chat.id, "") == "no_answer" and not message.text.startswith("/"))
def handle_no_answer(message):
    add_to_supervision_file(message.date, message.from_user.id, message.from_user.username,
                            f"{message.from_user.first_name} {message.from_user.last_name}",
                            message.chat.id, conversation_last_message[message.chat.id],
                            conversation_last_sentiments[message.chat.id], message.text)
    conversation_state[message.chat.id] = ""

    bot.reply_to(message, "Grazie per il tuo contributo!")


@bot.message_handler(
    func=lambda message: message.text.startswith("/annulla") and conversation_state[message.chat.id] != "")
def handle_cancel(message):
    conversation_state[message.chat.id] = ""
    bot.reply_to(message, "Come non detto allora. Inviami pure la prossima frase")


@bot.message_handler(func=lambda message: message.text[0] != "/")
def analyze_sentiment(message):
    logger.info(f"User {message.from_user.username} sent text: {message.text}")
    sentiments = parse_answer_sentiments(gpt_chat(message.text))
    conversation_last_message[message.chat.id] = message.text
    conversation_last_sentiments[message.chat.id] = sentiments

    bot.reply_to(message, create_formatted_message(message.chat.id, sentiments), parse_mode="markdown")


@bot.message_handler(commands=["analizza"])
def analyze_sentiment_by_command(message):
    text = parse_query(message.text)
    logger.info(f"User {message.from_user.username} sent /analizza command with text '{text}'")
    sentiments = parse_answer_sentiments(gpt_chat(text))

    bot.reply_to(message, create_formatted_message(message.chat.id, sentiments, supervised=False),
                 parse_mode="markdown")


@bot.message_handler(commands=["info"])
def get_info(message):
    bot.send_message(message.chat.id, "Ciao, io sono GPTEmotionsBot!\n"
                                      "Sono programmato per individuare le emozioni nelle frasi che mi vengono poste.\n"
                                      "Scrivimi pure una frase per farmela analizzare e al termine dell'analisi ti "
                                      "chiederò gentilmente di aiutarmi a capire se sono stato bravo.\n"
                                      "Se invece non vuoi aiutarmi a migliorare, puoi utilizzare il comando /analizza "
                                      "per pormi la frase da analizzare.\n"
                                      "È tutto, aspetto le tue frasi! :)")


bot.infinity_polling()
