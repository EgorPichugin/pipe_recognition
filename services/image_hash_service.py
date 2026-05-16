from hashlib import sha256


def create_image_hashvalue(image_bytes: bytes) -> str:
    return sha256(image_bytes).hexdigest()
