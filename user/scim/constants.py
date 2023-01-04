import http
import json

USER_NOT_FOUND_ERROR = json.dumps(
    {
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:Error"],
        "detail": "User not found",
        "status": http.HTTPStatus.NOT_FOUND,
    }
)
