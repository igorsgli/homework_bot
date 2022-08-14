class NoToken(Exception):
    """Отсутствие обязательных переменных
    окружения во время запуска бота.
    """

    pass

class HTTPstatusNot200(Exception):
    """Код ответа API не равен 200."""

    pass

class APINotAvailable(Exception):
    """API недоступен."""

    pass

class EmptyResponseFromAPI(Exception):
    """Домашней работы нет в ответе."""

    pass

class HomeworksIsNotList(Exception):
    """Формат полученных данных по домашним работам
    по ключу 'homeworks' не список.
    """

    pass
