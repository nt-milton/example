_search_models = []


def searchable_library_model(type, fields=[], qs=None, search_vector=None):
    def decorator(self, *args, **kwargs):
        _search_models.append(
            {
                'model': self,
                'fields': list(set(fields)),
                'type': type,
                'qs': qs,
                'search_vector': search_vector,
            }
        )
        return self

    return decorator


def exclude_duplicate_results(results):
    result_keys = []
    response = []
    for r in results:
        key = f'{r.get("id")}-{r.get("type")}'
        if key in result_keys:
            continue
        result_keys.append(key)
        response.append(r)
    return response
