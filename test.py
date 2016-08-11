n = 'fdfdf'


def validate(value):
    try:
        int(value)
        return True
    except ValueError:
        try:
            float(value)
            return True
        except ValueError:
            return False

print(validate(n))
