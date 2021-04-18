import datetime

import jwt


def assert_quick_response(response):
    """Make sure that a request doesn't take too long

    Args:
        response (requests.Response): response object
    """
    assert response.elapsed < datetime.timedelta(seconds=0.1)

def create_bearer_token():
    # Authorization: "bearer {test_login_token:s}"

    SECRET = "CGQgaG7GYvTcpaQZqosLy4"
    SERVERNAME = "testserver"

    payload = {
        "sub": "test-user",
        "aud": SERVERNAME,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1),
    }

    token = jwt.encode(payload, SECRET, algorithm="HS256")

    return {
        "Authorization": "Bearer {}".format(token)
    }
