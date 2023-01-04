from django.core.exceptions import ObjectDoesNotExist


class NoLaikaObjectsTypeException(ObjectDoesNotExist):
    pass
