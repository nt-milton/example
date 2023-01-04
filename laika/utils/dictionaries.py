def exclude_dict_keys(dic, keys):
    return {k: v for k, v in dic.items() if k not in keys}


class DictToClass(dict):
    """dot.notation access to dictionary attributes"""

    __getattr__ = dict.get
    __setattr__ = dict.__setitem__  # type: ignore
    __delattr__ = dict.__delitem__  # type: ignore
