import logging
from typing import Dict, Optional
import telebot
from telebot.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
import numpy as np
from scraper import get_player_stats
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from telebot.types import ReplyKeyboardRemove

user_states = {}  # {user_id: {state: str, data: {}}}
STATE_WAITING_FOR_NICKNAME = 'waiting_for_nickname'
STATE_WAITING_FOR_SUPPORT_MESSAGE = 'waiting_for_support_message'

def analyze_player_performance(stats: Dict) -> str:
    """Perform an analysis on the player's performance and format it as a message."""
    analysis = "<b>Анализ производительности:</b>\n\n"

    if stats.get('win_ratio') is not None:
        if stats['win_ratio'] > 70:
            analysis += "🏆 <b>Отличный результат!</b> Процент побед выше 70%. Вы настоящий чемпион!\n"
        elif stats['win_ratio'] > 50:
            analysis += "👍 <b>Хороший результат.</b> Процент побед больше 50%. Есть куда стремиться!\n"
        else:
            analysis += "😟 <b>Низкий процент побед.</b> Возможно, стоит пересмотреть стратегию игры.\n"

    if stats.get('apm') is not None:
        if stats['apm'] > 200:
            analysis += "⚡ <b>Высокий APM.</b> Ваши действия в игре очень быстрые!\n"
        elif stats['apm'] < 100:
            analysis += "🐢 <b>Низкий APM.</b> Попробуйте увеличить скорость действий.\n"

    if stats.get('leave_rate') is not None and stats['leave_rate'] > 10:
        analysis += "❗ <b>Высокий процент выходов из игр.</b> Постарайтесь завершать больше матчей.\n"

    analysis += "\n<i>Это предварительный анализ на основе доступных данных.</i>"
    return analysis

def format_stats_message(nickname: str, stats: Dict) -> str:
    """Format player stats into a readable message with each stat in a code block."""
    display_name = stats.get('username', nickname)
    message = f"<b>Статистика игрока {display_name}:</b>\n\n"

    # Проверяем статус игрока
    if stats.get('status') == "Нет игр":
        message += f"😢 <b>Игрок еще не сыграл ни одной игры</b>\n"
        message += f"\n<i>Данные получены с сайта iccup.com</i>"
        return message

    # Основные показатели
    if stats.get('pts'):
        message += f"<pre><code>PTS: {stats['pts']}</code></pre>\n"

    if stats.get('rank'):
        message += f"<pre><code>Ранг: {stats['rank']}</code></pre>\n"

    # Статистика игр
    if stats.get('games_played'):
        message += f"<pre><code>Всего игр: {stats['games_played']}</code></pre>\n"

        if stats.get('win_ratio') is not None:
            message += f"<pre><code>Процент побед: {stats['win_ratio']}%</code></pre>\n"

    if stats.get('wins') is not None and stats.get('losses') is not None:
        message += f"<pre><code>Победы/Поражения: {stats['wins']} / {stats['losses']}</code></pre>\n"

    # KDA
    if stats.get('average_kills') is not None:
        message += f"<pre><code>Среднее K/D/A: {stats.get('average_kills', 0)}/{stats.get('average_deaths', 0)}/{stats.get('average_assists', 0)}</code></pre>\n"

    # Локация
    if stats.get('location'):
        message += f"<pre><code>Локация: {stats['location']}</code></pre>\n"

    # Дополнительные данные
    additional_keys = [
        'apm', 'farm', 'experience_per_min', 'gank_participation',
        'total_match_time', 'avg_match_time', 'leave_rate'
    ]

    nice_names = {
        'apm': 'APM',
        'farm': 'Фарм',
        'experience_per_min': 'Опыт в минуту',
        'gank_participation': 'Участие в ганках',
        'total_match_time': 'Общее время матчей',
        'avg_match_time': 'Среднее время матча',
        'leave_rate': 'Процент выходов'
    }

    for key in additional_keys:
        if stats.get(key) is not None:
            display_name = nice_names.get(key, key.replace('_', ' ').title())
            value = stats[key]
            if isinstance(value, (float, int)) and 'rate' in key:
                value = f"{value}%"
            message += f"<pre><code>{display_name}: {value}</code></pre>\n"

    # Остальные неучтённые данные
    excluded_keys = ['username', 'pts', 'rank', 'games_played', 'win_ratio', 'wins', 'losses',
                     'average_kills', 'average_deaths', 'average_assists', 'location', 'status'] + additional_keys

    for key, value in stats.items():
        if key not in excluded_keys:
            display_name = key.replace('_', ' ').title()
            message += f"<pre><code>{display_name}: {value}</code></pre>\n"

    return message



def setup_bot(token: str) -> telebot.TeleBot:
    """Setup and return the bot instance."""
    bot = telebot.TeleBot(token)

    # Функция для создания главного меню
    def get_main_menu():
        markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        stats_btn = KeyboardButton('📈 Статистика игроков')
        contests_btn = KeyboardButton('🎉 Конкурсы')
        FAQ_btn = KeyboardButton('❓ FAQ')
        Tech_btn = KeyboardButton('🛠 Техническая поддержка')
        Vacancies_btn = KeyboardButton('Вакансии')
        markup.add(stats_btn, contests_btn, FAQ_btn, Tech_btn,Vacancies_btn)
        return markup


    # Обработчик команды /start
    @bot.message_handler(commands=['start'])
    def start_command(message: Message):
        """Sends a welcome message when the command /start is issued."""
        msg = f'Привет, {message.from_user.first_name}! 👋\n\nЯ бот для получения статистики игроков DotA с сайта iccup.com. С моей помощью вы можете быстро узнать рейтинг и достижения любого игрока!\n\nЧто я умею:\n• Получать статистику игроков по никнейму\n• Предоставлять полезную информацию об игре\n• Сообщать о новых конкурсах и событиях\n\nИспользуйте кнопки меню или команду /stats для начала работы.'
        bot.send_message(message.chat.id, msg, parse_mode='HTML', reply_markup=get_main_menu())

    # Обработчик команды /menu
    @bot.message_handler(commands=['menu'])
    def menu_command(message: Message):
        """Показывает главное меню"""
        bot.send_message(
            message.chat.id,
            'Главное меню:',
            parse_mode='HTML',
        )

    # Обработчик инлайн-кнопок
    @bot.callback_query_handler(func=lambda call: True)
    def handle_callback_query(call):
        """Обрабатывает нажатия на инлайн-кнопки"""
        # Извлекаем данные колбэка
        callback_data = call.data

        # Обработка информационных запросов
        if callback_data.startswith('info_'):
            # Получаем ключ для информации
            info_key = callback_data.split('_')[1]
            if info_key in INFO_DATABASE:
                bot.answer_callback_query(call.id)
                bot.send_message(call.message.chat.id, INFO_DATABASE[info_key], parse_mode='HTML')
            else:
                bot.answer_callback_query(call.id, "Информация не найдена", show_alert=True)

        # Возврат в главное меню
        elif callback_data == 'back_to_main':
            bot.answer_callback_query(call.id)
            bot.delete_message(call.message.chat.id, call.message.message_id)
            bot.send_message(call.message.chat.id, "Главное меню:", parse_mode='HTML', reply_markup=get_main_menu())

    # Обработчик команды /stats
    @bot.message_handler(commands=['stats'])
    def stats_command(message: Message):
        """Process the /stats command."""
        # Проверяем, есть ли параметр после команды
        command_parts = message.text.split()

        if len(command_parts) > 1:
            # Если есть параметр после команды, используем его как никнейм
            nickname = command_parts[1].strip()
            process_stats_request(message, nickname)
        else:
            # Если параметра нет, просим пользователя ввести никнейм
            msg = bot.send_message(
                message.chat.id,
                'Пожалуйста, введите никнейм игрока:',
                parse_mode='HTML'
            )
            # Устанавливаем состояние ожидания никнейма
            user_states[message.from_user.id] = {'state': STATE_WAITING_FOR_NICKNAME}
            # Регистрируем следующий шаг
            bot.register_next_step_handler(msg, process_nickname_input)

    # Обработчик ввода никнейма после команды /stats
    def process_nickname_input(message: Message):
        """Process nickname input after /stats command."""
        # Проверяем, что пользователь находится в нужном состоянии
        user_id = message.from_user.id

        if user_id in user_states and user_states[user_id]['state'] == STATE_WAITING_FOR_NICKNAME:
            # Получаем никнейм из сообщения
            nickname = message.text.strip()

            # Сбрасываем состояние пользователя
            user_states.pop(user_id, None)

            # Обрабатываем запрос статистики
            process_stats_request(message, nickname)
        else:
            # Если пользователь не в режиме ожидания никнейма, игнорируем сообщение
            pass


    # Функция обработки запроса статистики
    def process_stats_request(message: Message, nickname: str):
        """Process a statistics request for a given nickname."""
        # Логируем запрос
        logging.info(f"User {message.from_user.id} requested stats for '{nickname}'")

        # Показываем "печатает..." пока обрабатываем запрос
        bot.send_chat_action(message.chat.id, 'typing')

        try:
            # Получаем статистику игрока
            stats = get_player_stats(nickname)

            if stats:
                # Форматируем сообщение
                formatted_message = format_stats_message(nickname, stats)
                bot.send_message(message.chat.id, formatted_message, parse_mode='HTML')
            else:
                bot.send_message(
                    message.chat.id,
                    f'Не удалось найти игрока с никнеймом "{nickname}". '
                    f'Проверьте правильность написания и попробуйте снова.\n'
                    f'Используйте команду /stats для нового поиска.',
                    parse_mode='HTML',
                )
        except Exception as e:
            logging.error(f"Error processing stats for {nickname}: {str(e)}")
            bot.send_message(
                message.chat.id,
                'Произошла ошибка при получении статистики. Пожалуйста, попробуйте позже.\n'
                'Используйте команду /stats для нового поиска.',
                parse_mode='HTML',
            )

    # Обработчик команды /cancel
    @bot.message_handler(commands=['cancel'])
    def cancel_command(message: Message):
        """Cancel the current operation."""
        user_id = message.from_user.id

        # Сбрасываем состояние пользователя
        if user_id in user_states:
            user_states.pop(user_id, None)

        bot.send_message(
            message.chat.id,
            'Операция отменена. Вы в главном меню.',
            parse_mode='HTML',
        )

    # Обработчик текстовых сообщений (для обработки кнопок меню и других сообщений)
    @bot.message_handler(
        func=lambda message: message.text in ['📈 Статистика игроков', '🎉 Конкурсы' , '❓ FAQ', 'Вакансии', '🛠 Техническая поддержка'])
    def text_message_handler(message: Message):
        """Обрабатывает текстовые сообщения и нажатия на кнопки меню"""
        # Проверяем состояние пользователя
        user_id = message.from_user.id
        text = message.text.strip()

        # Если пользователь в состоянии ожидания ввода
        if user_id in user_states:
            state = user_states[user_id]['state']

            if state == STATE_WAITING_FOR_NICKNAME:
                # Если ожидается никнейм
                process_nickname_input(message)
                return

            elif state == STATE_WAITING_FOR_SUPPORT_MESSAGE:
                # Если ожидается сообщение для техподдержки
                process_support_message(message)
                return

        # Обработка нажатий на кнопки меню
        if text.startswith('📈 Статистика игроков'):
            # Запрашиваем ввод никнейма для получения статистики
            msg = bot.send_message(
                message.chat.id,
                'Пожалуйста, введите никнейм игрока:',
                parse_mode='HTML'
            )
            # Устанавливаем состояние ожидания никнейма
            user_states[user_id] = {'state': STATE_WAITING_FOR_NICKNAME}
            # Регистрируем следующий шаг
            bot.register_next_step_handler(msg, process_nickname_input)


        elif text.startswith('🎉 Конкурсы'):
            # Отправляем информацию о конкурсах
            contest_message = (
                " 🎮 DISCORD:\n"
                "🏆 Closed Games Вторник; Четверг; Суббота в 19:00 по МСК ⏰\n"
                "🔥 Приз за каждую выигранную игру 10 капсов💰 \n"
                "✅Подробности читайте в <a href='https://discord.com/channels/614513381600264202/890255824646176788'>канале дискорд</a>\n"
                "\n"
                "✈Telegram:\n"
                "<a href=https://t.me/iCCup/6989'>Актуальные конкурсы</a>\n"
                "\n"
                "🎯 FORUM конкурсы:\n"
                "Все актуальные конкурсы можете найти по  <a href=https://iccup.com/community/thread/1571455.html'>ссылке</a>\n"
                "\n"
                "CUSTOM конкурсы\n"
                "Понедельник , Вторник , Пятница Custom Closed Games \n"
                "Среда Custom Closed Wave!\n"
                "Суббота Custom Closed IMBA\n"
                "Воскресенье Custom Closed LOD\n"
                "Время проведения: 19:00 по МСК\n"
            )
            bot.send_message(message.chat.id, contest_message, parse_mode='HTML')

        elif text.startswith('Вакансии'):
            # Отправляем информацию о вакансии
            Vacancies_message = (
                "Social Media Marketing — разработка и развитие группы «Вконтакте» и на канале «Telegram», привлечение и удержание новых пользователей, общение с нашей аудиторией, создание уникального контента и проведение топовых эвентов с нашими юзерами.\n\n"
                "Зарплата 350 капсов в месяц\n\n"
                "Заинтересованы? <a href='https://t.me/Otsustvie_kreativa'>Обращайтесь</a>\n"
                "\n"
                "Forum Team — Создание качественного, креативного контента, модерация форума,\n"
                "поддержание чистоты и порядка, постоянное взаимодействие с игровым сообществом. Работа\n"
                "с аудиторией, направленная на улучшение качества общения.\n"
                "Заинтересованы? <a href='https://t.me/Absolutecinemas'>Обращайтесь</a>\n"
                "\n"
                "Design Team — создание баннеров для новостей, а также других элементов оформления сайта.\n"
                "— Работа с Photoshop и его аналогами на среднем уровне и выше.\n"
                "Заинтересовано? <a href='https://t.me/ula4svv'>Обращайтесь</a>\n"
                "\n"               
                "News — создание новостного мира платформы: красивый слог; абсолютное знание русского языка. Идут поиски ярких и неординарных индивидов, которые будут способны неустанно работать и хорошо зарабатывать.\n"
                "Заинтересовано? <a href='https://t.me/ula4svv'>Обращайтесь</a>\n"
                "\n"
                "Custom Maps Vacancy\n"
                "iCCup Custom League Team — Организация, создание и проведение турниров\n"
                "Custom Tournaments Team -  Проведение турниров Custom секции\n"
                "Custom Arena Team - Начисление очков pts участникам арены\n"
                "Closed Games Team - Знание карт из списка /chost. Вашей задачей будет проведение закрытых игр для пользователей\n"
                "Custom Forum Team - Порядок нужен везде, в особенности, на форуме\n"
                "Заинтересованы? <a href='https://iccup.com/job_custom_forum'>Мы ждем вас!</a>\n"
            )
            bot.send_message(message.chat.id, Vacancies_message, parse_mode='HTML')

        elif text.startswith('❓ FAQ'):
            # Отправляем информацию о FAQ
            faq_message = (
                "Q: Как создать аккаунт на iCCup?\n"
                "Ответ: <a href='https://t.me/iCCupTech/5'>Читайте тут</a>\n\n"

                "Q: Как начать играть?\n"
                "Ответ: <a href='https://t.me/iCCupTech/6'>Читайте тут</a>\n\n"

                "Q: Команды юзеров на сервере DotA:\n"
                "Ответ: <a href='https://t.me/iCCupTech/15'>Читайте тут</a>\n\n"

                "Q: Как работает рейтинг?\n"
                "Ответ: <a href='https://t.me/iCCupTech/16'>Читайте тут</a>\n\n"

                "Q: Какие есть правила iCCup'a?\n"
                "Ответ: <a href='https://t.me/iCCupTech/17'>Читайте тут</a>\n\n"

                "Q: Какие есть полезные ссылки?\n"
                "Ответ: <a href='https://t.me/iCCupTech/18'>Читайте тут</a>"
            )
            bot.send_message(message.chat.id, faq_message, parse_mode='HTML')

        elif text.startswith('🛠 Техническая поддержка'):
            # Tech supp
            Tech_message = (
                "Для получения более подробной и индивидуальной помощи обращайтесь в <a href='https://iccup.com/support_user/cat_ask/35.html'>раздел на сайте</a> .\n\n"
                "Q. <a href='https://t.me/iCCupTech/2'>Существуют ли версии лаунчера для Mac OS и unix?</a> .\n"
                "Q. <a href='https://t.me/iCCupTech/3'> Could not connect to Battle.Net/Не удалось установить соединение</a>.\n"
                "Q. <a href='https://t.me/iCCupTech/19'>Unable to Validate Game Version / Ошибка при проверке версии игры</a>.\n"
                "Q. <a href='https://t.me/iCCupTech/20'>Приложение не было запущено, поскольку оно некорректно настроено</a>.\n"
                "Q. <a href='https://t.me/iCCupTech/21'>Не найден файл iccwc3.icc</a>.\n"
                "Q. <a href='https://t.me/iCCupTech/22'>You Broke It / Что-то пошло не так</a>.\n"
                "Q. <a href='https://t.me/iCCupTech/23'>That account does not exist / Учётной записи с таким именем не существует</a>.\n"
                "Q. <a href='https://t.me/iCCupTech/24'>Нет меню в Варкрафте</a>.\n"
                "Q. <a href='https://t.me/iCCupTech/25'>Ошибка «Could not open game.dll»</a>.\n"
                "Q. <a href='https://t.me/iCCupTech/26'>Ошибка при попытке сохранения данных, загруженных с Battle.Net</a>.\n"
                "Q. <a href='https://t.me/iCCupTech/27'>Не удалось инициализировать DirectX</a>.\n"
                "Q. <a href='https://t.me/iCCupTech/28'>Неверный компакт диск</a>.\n"
                "Q. <a href='https://t.me/iCCupTech/29'>Розово-чёрные квадраты / нет анимации некоторых умений</a>.\n"
                "Q. <a href='https://t.me/iCCupTech/30'>Crash it. FATAL ERROR</a>.\n"
                "Q. <a href='https://t.me/iCCupTech/31'>Капюшоны в батлнете</a>.\n"
                "Q. <a href='https://t.me/iCCupTech/32'>Ошибка ввода пароля три раза подряд</a>.\n"
                "Q. <a href='https://t.me/iCCupTech/33'>Ошибки с ACCESS VIOLATION</a>.\n"
                "Q. <a href='https://t.me/iCCupTech/34'>Не работают хоткеи</a>.\n"
            )
            bot.send_message(message.chat.id, Tech_message, parse_mode='HTML')

        else:
            # Если не распознали команду - показываем подсказку
            bot.send_message(
                message.chat.id,
                'Для взаимодействия с ботом используйте кнопки меню или следующие команды:\n'
                '/start - главное меню\n'
                '/menu - показать меню\n'
                '/stats - получить статистику игрока\n'
                '/cancel - отменить текущую операцию',
                parse_mode='HTML',
            )

    return bot