import json
from functools import wraps

import requests
from apiflask import HTTPTokenAuth
from flask import request, Response

from config import WebConfig, IBMSecurityConfig
from ibm.common.consts import AUTH_LINK, SUBSCRIPTION_LINK, SUBSCRIPTION_STATUS_PAYLOAD

auth = HTTPTokenAuth()


def authenticate(func):
    """Validate token."""

    @wraps(func)
    def authenticate_and_call(*args, **kwargs):
        auth_header = request.headers.get('Authorization', type=str)
        project_id = request.headers.get('project-id', type=str)
        if not auth_header:
            return Response(status=401)

        split_auth_header = auth_header.split()
        if not len(split_auth_header) == 2:
            return Response(status=401)

        token = split_auth_header[1]
        headers = {'Authorization': f"Bearer {token}"}
        if project_id:
            headers["project_id"] = project_id

        resp = requests.get(url=AUTH_LINK, headers=headers)
        if not resp or resp.status_code != 200:
            return Response(status=401)

        if project_id:
            resp.json()["project_id"] = project_id

        kwargs['user'] = resp.json()

        if WebConfig.IS_MULTI_TENANCY_ENABLE:
            subscription_resp = requests.get(url=f"{SUBSCRIPTION_LINK}{project_id}", headers=headers)

            if not subscription_resp.json() or len(subscription_resp.json()) == 0:
                return Response(json.dumps(SUBSCRIPTION_STATUS_PAYLOAD), status=403, mimetype="application/json")

        return func(*args, **kwargs)

    return authenticate_and_call


@auth.verify_token
def verify_token(token):
    resp = requests.get(url=AUTH_LINK, headers={'Authorization': f"Bearer {token}"})
    if not resp or resp.status_code != 200:
        return False

    return resp.json()


def authorize_admin(func):
    """Authorize Admin."""

    @wraps(func)
    def authorize_admin_and_call(*args, **kwargs):
        is_admin = kwargs['user'].get("is_admin", False)
        if not is_admin:
            return Response(status=401)
        return func(*args, **kwargs)

    return authorize_admin_and_call


def authenticate_api_key(func):
    """Validate API-KEY"""

    @wraps(func)
    def authenticate_and_call(*args, **kwargs):
        auth_token = request.headers.get('X-Api-Key', type=str)
        if not auth_token:
            return Response(status=401)

        elif auth_token != IBMSecurityConfig.IBM_ENV_X_API_KEY:
            return Response(status=401)

        else:
            return func(*args, **kwargs)

    return authenticate_and_call
