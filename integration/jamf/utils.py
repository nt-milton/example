import re

# Device Types
from laika.utils.regex import ONLY_NUMBERS

DESKTOP = 'Desktop'
LAPTOP = 'Laptop'
MOBILE = 'Mobile'
PRINTER = 'Printer'
OTHERS = 'Others'

# Encryption Status
ENCRYPTED = 'Encrypted'
NOT_ENCRYPTED = 'Not encrypted'
NA = 'N/A'

# Issuance Status
ISSUED = 'Issued'
IN_INVENTORY = 'In Inventory'
LOST = 'Lost'

# REGEX DOMAIN FORMAT
SUB_DOMAIN_REGEX = r'[a-zA-Z0-9]+\.jamfcloud\.com'
VALID_DOMAIN_REGEX = r'^[a-zA-Z]+$'


def get_device_type(model):
    device_type = OTHERS
    if model:
        if 'iMac' in model or 'mini' in model:
            device_type = DESKTOP
        elif 'MacBook' in model:
            device_type = LAPTOP
    return device_type


def get_computer_encryption_status(encryption_details):
    if not encryption_details:
        return NA
    vault_state = encryption_details.get('partitionFileVault2State')
    return ENCRYPTED if vault_state in ['VALID', 'ENCRYPTED'] else NOT_ENCRYPTED


def get_mobile_encryption_status(device_security):
    if not device_security:
        return NA
    return (
        ENCRYPTED if device_security['blockLevelEncryptionCapable'] else NOT_ENCRYPTED
    )


def extract_price(str_price):
    if str_price is None:
        return 0
    return int(re.sub(ONLY_NUMBERS, '', str_price))


def format_location(*, department, building, room):
    location = filter(bool, [department, building, room])
    return ", ".join(location)
