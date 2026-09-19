class MealieError(RuntimeError):
    """Safe base error. Messages must not contain upstream bodies or credentials."""


class MealieUnauthorized(MealieError):
    pass


class MealieForbidden(MealieError):
    pass


class MealieNotFound(MealieError):
    pass


class MealieConnectionNotConfigured(MealieNotFound):
    """The authenticated principal has no default Mealie connection."""


class MealieUnavailable(MealieError):
    pass


class MealieInvalidResponse(MealieError):
    pass


class CapabilityUnavailable(MealieError):
    pass
