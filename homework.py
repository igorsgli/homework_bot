import exceptions
import logging
import os
import requests
import sys
import telegram
import time

from dotenv import load_dotenv

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


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

My = exceptions.My()


def send_message(bot, message):
    """Отправляет сообщние в Telegram чат, определяемый переменной окружения TELEGRAM_CHAT_ID."""
    try:
        sent_message = bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception as error:
        logger.error(
            f'Сбой при отправке сообщения в Telegram: "{error}"'
        )
    else:
        if sent_message.text == message:
            logger.info(
                f'Бот отправил сообщение: "{message}"'
            )
        else:
            logger.info(
                f'Бот отправил другое сообщение: "{sent_message.text}"'
                f'А должно было быть отправлено сообщение: "{message}"'
            )


def get_api_answer(current_timestamp):
    """Делает запрос к единственному
    эндпоинту API-сервиса.
    """
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}

    homework_statuses = requests.get(ENDPOINT, headers=HEADERS, params=params)
    if homework_statuses.status_code != 200:
        raise My.HTTPstatusNot200('API возвращает код, отличный от 200')

    return homework_statuses.json()


def check_response(response):
    """Проверяет ответ API на корректность."""
    keys = dict.keys(response)
    if 'homeworks' in keys and 'current_date' in keys:
        homeworks = response['homeworks']
        if isinstance(homeworks, list):
            return homeworks
        else:
            raise My.HomeworksIsNotList(
                'Возвращается не список домашних работ.'
            )
    else:
        raise My.NoKeysException('Отсутствуют ожидаемые ключи в ответе API.')


def parse_status(homework):
    """Извлекает из информации о конкретной
    домашней работе статус этой работы.
    """
    homework_name = homework['homework_name']
    homework_status = homework['status']
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность переменных окружения,
    которые необходимы для работы бота.
    """
    if (
        PRACTICUM_TOKEN is not None
        and TELEGRAM_TOKEN is not None
        and TELEGRAM_CHAT_ID is not None
    ):
        return True
    else:
        return False


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        for token, name in (
            (PRACTICUM_TOKEN, 'PRACTICUM_TOKEN'),
            (TELEGRAM_TOKEN, 'TELEGRAM_TOKEN'),
            (TELEGRAM_CHAT_ID, 'TELEGRAM_CHAT_ID'),
        ):
            if token is None:
                logger.critical(
                    f'Отсутствует обязательная переменная '
                    f'окружения: "{name}". '
                    f'Программа принудительно остановлена.'
                )
        raise My.NoTokenException(
            'Отсутствуют обязательные переменные окружения'
        )

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    status_verdict_previous = ''
    HTTP_error_previous = ''
    endpoint_message_previous = ''
    error_not_list_previous = ''
    error_no_keys_previous = ''
    error_status_previous = ''

    while True:
        try:
            response = get_api_answer(current_timestamp)

        except My.HTTPstatusNot200 as error:
            HTTP_error = f'Сбой в програме: ответ API: "{error}".'
            logger.error(HTTP_error)
            if HTTP_error != HTTP_error_previous:
                send_message(bot, HTTP_error)
                HTTP_error_previous = HTTP_error
            time.sleep(RETRY_TIME)

        except Exception as error:
            endpoint_message = (
                f'Сбой в работе программы: Эндпоинт: {ENDPOINT} недоступен. '
                f'Ответ API: {error}'
            )
            logger.error(endpoint_message)
            if endpoint_message != endpoint_message_previous:
                send_message(bot, endpoint_message)
                endpoint_message_previous = endpoint_message
            time.sleep(RETRY_TIME)

        else:
            try:
                homeworks = check_response(response)

            except My.HomeworksIsNotList as error:
                error_not_list = f'Сбой в программе: "{error}"'
                logger.error(error_not_list)
                if error_not_list != error_not_list_previous:
                    send_message(bot, error_not_list)
                    error_not_list_previous = error_not_list
                    time.sleep(RETRY_TIME)

            except My.NoKeysException as error:
                error_no_keys = f'Сбой в программе: "{error}"'
                logger.error(error_no_keys)
                if error_no_keys != error_no_keys_previous:
                    send_message(bot, error_no_keys)
                    error_no_keys_previous = error_no_keys

                    time.sleep(RETRY_TIME)

            else:
                if homeworks == []:
                    status_verdict = 'Статус отсутствует.'
                else:
                    try:
                        status_verdict = parse_status(homeworks[0])
                        print(status_verdict)
                    except Exception as error:
                        error_status = (
                            f'Сбой в работе программы: '
                            f'Статус домашней работы незадокументирован. '
                            f'Ответ API: {error}'
                        )
                        logger.error(error_status)
                        if error_status != error_status_previous:
                            send_message(bot, error_status)
                            error_status_previous = error_status

                        time.sleep(RETRY_TIME)

                if status_verdict != status_verdict_previous:
                    send_message(bot, status_verdict)
                    status_verdict_previous = status_verdict
                else:
                    logger.debug('В ответе отсутствуют новые статусы.')

                time.sleep(RETRY_TIME)
                current_timestamp = response['current_date']


if __name__ == '__main__':
    main()
