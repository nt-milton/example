from audit.constants import SOC_2_TYPE_1


def get_description_by_type(type):
    if type == SOC_2_TYPE_1:
        return (
            "The purpose of this AICPA report is to conduct a "
            "formalized SOC examination. The report includes "
            "management's description of the system as well as the "
            "suitability of the design of controls as of a specific "
            "point in time."
        )
    return (
        "The purpose of this AICPA report is to conduct a "
        "formalized SOC examination. The report includes "
        "management's description of the system as well as the "
        "suitability of both the design and operating effectiveness "
        "of controls over a period of time."
    )
