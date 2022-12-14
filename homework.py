import exceptions
import logging
import os
import requests
import telegram
import time

from dotenv import load_dotenv
from http import HTTPStatus

load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler('x.log', encoding='utf-8')
logger.addHandler(handler)
formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s - %(lineno)d'
)
handler.setFormatter(formatter)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Отправляет сообщние в Telegram чат."""
    try:
        logger.info(f'Бот начинает отправку сообщения: "{message}"')
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except telegram.error.TelegramError as error:
        logger.error(
            f'Сбой при отправке сообщения в Telegram: "{error}"'
        )
    else:
        logger.info(
            f'Бот отправил сообщение: "{message}"'
        )


def get_api_answer(current_timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    timestamp = current_timestamp
    params = {'from_date': timestamp}
    request_args = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': params,
    }
    try:
        logger.info(
            f'Начинаем запрос к API: '
            f'{"{url}, {headers}, {params}".format(**request_args)}'
        )
        homework_statuses = requests.get(**request_args)
        if homework_statuses.status_code != HTTPStatus.OK:
            raise exceptions.HTTPstatusNot200(
                f'API возвращает код, отличный от 200. '
                f'Код ответа: {homework_statuses.status_code}. '
                f'Причина: {homework_statuses.reason}. '
                f'Текст: {homework_statuses.text}.'
            )
        logger.info('Ответ от API пришел.')
        return homework_statuses.json()
    except Exception as error:
        raise ConnectionError(
            f'Сбой в програме при запросе API: "{error}". '
            f'Запрос к API: '
            f'{"{url}, {headers}, {params}".format(**request_args)}. '
            f'Ответ API: "{error}".'
        )


def check_response(response):
    """Проверяет ответ API на корректность."""
    logger.info('Начало проверки ответа API.')
    if not isinstance(response, dict):
        raise TypeError(
            'Возвращаемый ответ не словарь.'
        )
    if 'homeworks' not in response:
        raise exceptions.EmptyResponseFromAPI(
            'Домашней работы нет в ответе.'
        )
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise exceptions.HomeworksIsNotList(
            'Возвращаемая домашняя работа не список.'
        )
    logger.info('Ответ API проверен.')
    return homeworks


def parse_status(homework):
    """Извлекает статус домашней работы."""
    logger.info('Начало извлечения статуса домашней работы.')
    if 'homework_name' not in homework:
        raise KeyError(
            'Ключ "homework_name" отсутствует в домашней работе.'
        )
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_VERDICTS:
        raise KeyError(
            'Неожиданный статус домашней работы.'
        )
    logger.info('Статус домашней работы извлечен.')
    return (
        f'Изменился статус проверки работы "{homework_name}". '
        f'{HOMEWORK_VERDICTS[homework_status]}'
    )


def check_tokens():
    """Проверяет доступность переменных окружения."""
    is_tokens_available = True
    for token, name in (
        (PRACTICUM_TOKEN, 'PRACTICUM_TOKEN'),
        (TELEGRAM_TOKEN, 'TELEGRAM_TOKEN'),
        (TELEGRAM_CHAT_ID, 'TELEGRAM_CHAT_ID'),
    ):
        if token is None:
            is_tokens_available = False
            logger.critical(
                f'Отсутствует обязательная переменная '
                f'окружения: "{name}". '
                f'Программа принудительно остановлена.'
            )
    return is_tokens_available


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        raise exceptions.NoToken(
            'Отсутствуют обязательные переменные окружения'
        )
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    current_report = {'name': '', 'output': ''}
    prev_report = {'name': '', 'output': ''}

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)

            if homeworks:
                current_report['output'] = parse_status(homeworks[0])
                current_report['name'] = homeworks[0]['homework_name']
            else:
                current_report['output'] = 'Нет новых статусов.'

            if current_report != prev_report:
                send_message(bot, current_report['output'])
                prev_report = current_report.copy()
                current_timestamp = response.get(
                    'current_date', current_timestamp
                )
            else:
                logger.info('Новые статусы отсутствуют.')

        except exceptions.EmptyResponseFromAPI as error:
            logger.error(error)

        except Exception as error:
            logger.error(error)
            current_report['output'] = error
            if current_report != prev_report:
                send_message(bot, current_report['output'])
                prev_report = current_report.copy()

        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
