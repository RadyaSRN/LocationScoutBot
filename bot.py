import shutil
import requests
import telebot
import openai
from telebot import types
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains

openai.api_key = 'your-OpenAI-API-key'

bot = telebot.TeleBot('your-bot-API-key')

place_id_to_url_map = dict()
place_id_to_name_map = dict()
total_place_counter = 0


@bot.message_handler(commands=['start'])
def greet_user(message):
    """Starts the bot, greets user.

    Adds two buttons to the greeting message so that user can start interacting with the bot.

    Args:
      message: contains '/start' command.
    """

    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    button1 = types.KeyboardButton(text="Найти интересующие меня места")
    button2 = types.KeyboardButton(text="Найти случайные интересные места")
    keyboard.add(button1, button2)
    bot.send_message(message.chat.id, "Привет! Это *Location Scout Bot*. Я умею находить *интересные места* в *заданной Вами локации*.", parse_mode="Markdown", reply_markup=keyboard)


@bot.message_handler(commands=['help'])
def show_commands(message):
    """Show the list of all commands.

    Args:
      message: contains '/help' command.
    """

    bot.send_message(message.chat.id, "Вот список моих комманд:\n\n/start - активировать меня\n/help - получить список моих команд\n/scout - найти интересующие Вас места в заданной Вами локации\n/scout_random - найти случайные интересные места в заданной Вами локации")


@bot.message_handler(commands=['scout'])
@bot.message_handler(func=lambda message: message.text == "Найти интересующие меня места")
def scout_handler(message):
    """Asks user for a location where the bot has to search for places.

    Gets message from a user and forwards it to query_handler.

    Args:
      message: contains either '/scout' command or text that was generated by a user clicking on
        a keyboard button.
    """

    text = "В какой *локации* я должен искать *интересующие Вас* места?"
    keyboard = types.ReplyKeyboardRemove()
    received_message = bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=keyboard)
    bot.register_next_step_handler(received_message, query_handler)


@bot.message_handler(commands=['scout_random'])
@bot.message_handler(func=lambda message: message.text == "Найти случайные интересные места")
def scout_random_handler(message):
    """Asks user for a location where the bot has to search for random places.

    Gets message from a user and forwards it to random_query_handler.

    Args:
      message: contains either '/scout_random' command or text that was generated by a user clicking on
        a keyboard button.
    """

    text = "В какой *локации* я должен искать интересные места?"
    keyboard = types.ReplyKeyboardRemove()
    received_message = bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=keyboard)
    bot.register_next_step_handler(received_message, random_query_handler)


def query_handler(message):
    """Asks user for places to search for.

    Gets response from user, then forwards the query and the location to get_results_for_location.

    Args:
      message: contains the location where the bot will be looking for places.
    """

    location = message.text
    text = "Что *Вас интересует* в данной локации?"
    received_message = bot.send_message(message.chat.id, text, parse_mode="Markdown")
    bot.register_next_step_handler(received_message, get_results_for_location, location)


def random_query_handler(message):
    """Generates query with places using OpenAI's Davinci model.

    First, gets the response from the model. Then filters it by excluding punctuation marks and
    forwards the query and the location to get_results_for_location.

    Args:
      message: contains the location where the bot will be looking for places.
    """

    location = message.text
    try:
        model_response = openai.Completion.create(
            model="text-davinci-003",
            prompt="""Q: Suggest some interesting types of restaurants or places to visit in a new city, for example: "famous museums", "french restaurants". Name of the city does not matter. There should be at most two words in the answer. Answer in Russian\nA:""",
            temperature=0.3,
            max_tokens=100,
            top_p=1,
            frequency_penalty=0.0,
            presence_penalty=0.0,
            stop=["\n"]
        )
    except Exception as e:
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
        button1 = types.KeyboardButton(text="Найти интересующие меня места")
        button2 = types.KeyboardButton(text="Найти случайные интересные места")
        keyboard.add(button1, button2)
        bot.send_message(message.chat.id, "У меня не получилось придумать ничего интересного для поиска...", parse_mode="Markdown", reply_markup=keyboard)
        return
    model_response_text = model_response["choices"][0]["text"]
    punctuation_marks = [",", ".", "(", ")"]
    for punctuation_mark in punctuation_marks:
        model_response_text = model_response_text.replace(punctuation_mark, " ")
    bot.send_message(message.chat.id, f"Я буду искать следующие места: *{model_response_text}*", parse_mode="Markdown")
    message.text = model_response_text
    get_results_for_location(message, location)


def get_results_for_location(message, location):
    """Finds places listed in the message in the specified location.

    First, performs the search in Google Maps. Then goes through all places from the search result
    and sends the following data for each place to a user: photo, name, rating, review count. Adds two buttons
    to each such message: one with the place's URl, another one with the callback that once triggerred sends
    the place's reviews. In the end sends the message stating that the search is over, this message comes with
    two buttons so that user can keep interacting.

    Args:
      message: contains the query from a user.
      location: specifies the location where the bot has to look for places.
    """

    bot.send_message(message.chat.id, "Начинаю поиск... Я сообщу вам, когда выведу все найденные результаты.", parse_mode="Markdown")
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    browser = webdriver.Chrome(options=options)
    actions = ActionChains(browser)
    query = message.text
    location = location.replace(" ", "+")
    query = query.replace(" ", "+")
    url = f"https://www.google.ru/maps/search/{location}+{query}"
    browser.get(url)
    places = browser.find_elements(By.CLASS_NAME, "hfpxzc")
    places_len = len(places)
    place_counter = 0
    for i in range(places_len):
        try:
            browser.get(url)
            places = browser.find_elements(By.CLASS_NAME, "hfpxzc")
            place_name = places[i].get_attribute("aria-label")
            place_parent = places[i].find_element(By.XPATH, "..")
            try:
                place_rating_element = place_parent.find_element(By.CLASS_NAME, "ZkP5Je")
            except Exception as e:
                continue
            place_rating = place_rating_element.get_attribute("aria-label")[:3]
            place_review_count = place_rating_element.get_attribute("aria-label")[24:]
            place_information = f"*{place_name}*" + "\n" + f"""Рейтинг: {place_rating} (отзывов: {place_review_count})\n"""
            place_url = places[i].get_attribute("href")
            browser.get(place_url)
            try:
                button = browser.find_element(By.CLASS_NAME, "ofKBgf")
            except Exception as e:
                continue
            actions.move_to_element(button).perform()
            button.click()
            image_element_parent = WebDriverWait(browser, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "U39Pmb")))
            actions.move_to_element(image_element_parent).perform()
            image_element = WebDriverWait(browser, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".Uf0tqf.loaded")))
            image_url = image_element.get_attribute("style").split()[5][5:-3]
            response = requests.get(image_url, stream=True)
            with open('image.png', 'wb') as out_file:
                shutil.copyfileobj(response.raw, out_file)
            del response
            keyboard = types.InlineKeyboardMarkup(row_width=1)
            keyboard_url_button = types.InlineKeyboardButton(text="Посмотреть всю информацию", url=place_url)
            global total_place_counter
            keyboard_reviews_button = types.InlineKeyboardButton(text="Получить отзывы", callback_data=str(total_place_counter))
            place_id_to_url_map[total_place_counter] = place_url
            place_id_to_name_map[total_place_counter] = place_name
            keyboard.add(keyboard_url_button, keyboard_reviews_button)
            bot.send_photo(message.chat.id, photo=open('image.png', 'rb'), caption=place_information, parse_mode="Markdown", reply_markup=keyboard)
            place_counter += 1
            total_place_counter += 1
        except Exception as e:
            continue
    text = ""
    if place_counter == 0:
        text = "*Ничего* не нашлось!"
    else:
        text = "Это *все места*, что я нашел!"
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    button1 = types.KeyboardButton(text="Найти интересующие меня места")
    button2 = types.KeyboardButton(text="Найти случайные интересные места")
    keyboard.add(button1, button2)
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=keyboard)
    browser.quit()


@bot.callback_query_handler(func=lambda callback: callback.data)
def process_get_reviews_callback(callback):
    """Get reviews for the given place.

    First retrieves the place's name and URL from dictionaries. Then goes to that URL, expands every review
    and sends review information to a user.

    Args:
      callback: callback from a button clicked by a user.
    """

    place_id = int(callback.data)
    try:
        place_url = place_id_to_url_map[place_id]
    except Exception as e:
        bot.send_message(callback.message.chat.id, "Не могу найти отзывов у того места!", parse_mode="Markdown")
        return
    place_name = place_id_to_name_map[place_id]
    bot.send_message(callback.message.chat.id, f"Начинаю искать отзывы для *{place_name}*...", parse_mode="Markdown")
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    browser = webdriver.Chrome(options=options)
    actions = ActionChains(browser)
    browser.get(place_url)
    for i in range(3):
        try:
            button = browser.find_element(By.CSS_SELECTOR, ".w8nwRe.kyuRq")
            actions.move_to_element(button).perform()
            button.click()
        except Exception as e:
            continue
    try:
        reviews = browser.find_elements(By.CSS_SELECTOR, ".jftiEf.fontBodyMedium")
        text = f"Вот отзывы, которые я нашел для *{place_name}*:\n\n"
        reviews_len = len(reviews)
        for i in range(reviews_len):
            actions.move_to_element(reviews[i]).perform()
            review_author = reviews[i].find_element(By.CLASS_NAME, "d4r55").text
            review_text = reviews[i].find_element(By.CLASS_NAME, "wiI7pd").text
            text += f"*{review_author}*\n"
            text += review_text + "\n\n"
        bot.send_message(callback.message.chat.id, text, parse_mode="Markdown")
    except Exception as e:
        bot.send_message(callback.message.chat.id, "Не могу найти отзывов у того места!", parse_mode="Markdown")
    browser.quit()


bot.infinity_polling()

