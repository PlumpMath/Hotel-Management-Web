class APIError(Exception):
    def __init__(self, error, data='', message=''):
        super().__init__(error, data, message)


class APIValueError(APIError):
    def __init__(self, field, message=''):
        super().__init__('Value: invalid', field, message)
