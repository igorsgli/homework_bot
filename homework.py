import exceptions
import logging
import os
import requests
import sys
import telegram
import time

from dotenv import load_dotenv
from http import HTTPStatus

load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
logger.addHandler(handler)
formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s'
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
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params
        )
        if homework_statuses.status_code != HTTPStatus.OK:
            raise exceptions.HTTPstatusNot200(
                f'API возвращает код, отличный от 200. '
                f'Код ответа: {homework_statuses.status_code}. '
                f'Причина: {homework_statuses.reason}. '
                f'Текст: {homework_statuses.text}.'
            )
        logger.info('Ответ от API пришел.')
        return homework_statuses.json()
    except ConnectionError as error:
        raise exceptions.APINotAvailable(
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
    if response.get('homeworks') == []:
        raise exceptions.EmptyResponseFromAPI(
            'Домашней работы нет в ответе.'
        )
    homeworks = response.get('homeworks')
    if isinstance(homeworks, list):
        logger.info('Ответ API проверен.')
        return homeworks
    else:
        raise exceptions.HomeworksIsNotList(
            'Возвращаемая домашняя работа не список.'
        )


def parse_status(homework):
    """Извлекает статус домашней работы."""
    logger.info('Начало извлечения статуса домашней работы.')
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_VERDICTS:
        raise KeyError(
            'Неожиданный статус домашней работы.'
        )        
    else:
        logger.info('Статус домашней работы извлечен.')
        return (
            f'Изменился статус проверки работы "{homework_name}". {HOMEWORK_VERDICTS[homework_status]}'
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
    current_report = {'verdict': '', 'error': ''}
    prev_report = current_report.copy()

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            current_report['verdict'] = parse_status(homeworks[0])
            if current_report['verdict'] != prev_report['verdict']:
                send_message(bot, current_report['verdict'])
                prev_report = current_report.copy()
                current_timestamp = response['current_date']
            else:
                logger.info('Новые статусы отсутствуют.')

        except exceptions.EmptyResponseFromAPI as error:
            logger.error(error)

        except Exception as error:
            logger.error(error)
            current_report['error'] = error
            if current_report['error'] != prev_report['error']:
                send_message(bot, current_report['error'])
                prev_report = current_report.copy()

        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
