class ImageCheckError(Exception):
    pass


class ImageAuthenticationError(ImageCheckError):
    pass


class ImageNameError(ImageCheckError):
    pass
