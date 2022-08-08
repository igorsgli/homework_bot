class My(object):
    """Собственные исключения."""

    class NoTokenException(Exception):
        """Отсутствие обязательных переменных
        окружения во время запуска бота.
        """

        pass

    class HTTPstatusNot200(Exception):
        """Код ответа API не равен 200."""

        pass

    class NoKeysException(Exception):
        """Отсутствие ожидаемых ключей
        в ответе API.
        """

        pass

    class HomeworksIsNotList(Exception):
        """Формат полученных данных по домашним работам
        по ключу 'homeworks' не список.
        """

        pass
